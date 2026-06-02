from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.db import base  # noqa: F401
from app.db.session import SessionLocal
from app.importers.legacy_company_tsv import truthy_int
from app.importers.legacy_customers import clean_text, to_decimal
from app.models.customer import Customer
from app.models.sales import SalesOrder, SalesOrderItem

csv.field_size_limit(sys.maxsize)


BILL_HEADERS_WITH_RID = [
    "ID",
    "RID",
    "BillID",
    "DateBill",
    "CompanyID",
    "Total",
    "SaleMan",
    "ProductName",
    "ProductPlanID",
    "Remarks",
    "TechType",
    "State",
    "DeliveryTime",
    "BringDiameter",
    "AlwayCount",
    "BringCount",
    "NewCount",
    "StockCount",
    "CorSquRoller",
    "PrintingMode",
    "BagMakway",
    "ActualSize",
    "Increasing",
    "ProSpecify",
    "PS",
    "PSM",
    "PAW",
    "BillingNote",
    "ProductNote",
    "RegNumber",
    "JsTotal",
    "ZPrice",
    "DeliTime",
    "FHTime",
    "FHName",
    "CostTotal",
    "SHBillID",
    "CWState",
    "PPrice",
    "PCostPrice",
    "CreateTime",
    "UpdateTime",
    "Deleted",
    "KHTSYQ",
    "KeySize",
    "CustomerNote",
    "CopperThick",
    "YSALEMAN",
]

BILL_HEADERS = [header for header in BILL_HEADERS_WITH_RID if header != "RID"]


def read_bills_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as file:
        raw_rows = list(csv.reader(file, delimiter="\t"))
    if not raw_rows:
        return []

    first_row = [cell.strip() for cell in raw_rows[0]]
    has_header = "BillID" in first_row and "DateBill" in first_row
    if has_header:
        headers = first_row
        data_rows = raw_rows[1:]
    elif len(first_row) == len(BILL_HEADERS_WITH_RID):
        headers = BILL_HEADERS_WITH_RID
        data_rows = raw_rows
    else:
        headers = BILL_HEADERS
        data_rows = raw_rows

    rows: list[dict[str, str]] = []
    for row in data_rows:
        if not row:
            continue
        first_cell = row[0].strip()
        if first_cell.startswith("--") or first_cell.startswith("("):
            continue
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        elif len(row) > len(headers):
            row = row[: len(headers) - 1] + [" ".join(row[len(headers) - 1 :])]
        values = {headers[index]: row[index].strip() for index in range(len(headers))}
        if any(values.values()):
            rows.append(values)
    return rows


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    candidates = [
        text[:10],
        text.replace("/", "-")[:10],
    ]
    for candidate in candidates:
        try:
            return datetime.strptime(candidate, "%Y-%m-%d").date()
        except ValueError:
            continue
    return None


def positive_decimal(*values: Any) -> Decimal:
    for value in values:
        amount = to_decimal(value)
        if amount and amount > 0:
            return amount
    return Decimal("0")


def quantity_from_row(row: dict[str, str]) -> Decimal:
    quantity = positive_decimal(row.get("AlwayCount"))
    if quantity > 0:
        return quantity
    parts = [
        to_decimal(row.get("BringCount")) or Decimal("0"),
        to_decimal(row.get("NewCount")) or Decimal("0"),
        to_decimal(row.get("StockCount")) or Decimal("0"),
    ]
    total = sum(parts, Decimal("0"))
    return total if total > 0 else Decimal("1")


def unit_price(amount: Decimal, quantity: Decimal) -> Decimal:
    if quantity <= 0:
        return amount
    try:
        return (amount / quantity).quantize(Decimal("0.01"))
    except (InvalidOperation, ZeroDivisionError):
        return Decimal("0")


def compact_parts(parts: list[str | None]) -> str | None:
    values = [part for part in parts if part]
    return "; ".join(values) if values else None


def specification_from_row(row: dict[str, str]) -> str | None:
    return compact_parts(
        [
            f"ProSpecify={clean_text(row.get('ProSpecify'), 80)}" if clean_text(row.get("ProSpecify")) else None,
            f"ActualSize={clean_text(row.get('ActualSize'), 40)}" if clean_text(row.get("ActualSize")) else None,
            f"Diameter={clean_text(row.get('BringDiameter'), 40)}" if clean_text(row.get("BringDiameter")) else None,
            f"CopperThick={clean_text(row.get('CopperThick'), 40)}" if clean_text(row.get("CopperThick")) else None,
            f"Print={clean_text(row.get('PrintingMode'), 80)}" if clean_text(row.get("PrintingMode")) else None,
            f"Bag={clean_text(row.get('BagMakway'), 80)}" if clean_text(row.get("BagMakway")) else None,
            f"KeySize={clean_text(row.get('KeySize'), 80)}" if clean_text(row.get("KeySize")) else None,
        ]
    )


def remark_from_row(row: dict[str, str]) -> str:
    fields = [
        ("Legacy B_BussinessMst.ID", "ID"),
        ("Legacy CompanyID", "CompanyID"),
        ("Legacy State", "State"),
        ("TechType", "TechType"),
        ("ProductPlanID", "ProductPlanID"),
        ("RegNumber", "RegNumber"),
        ("CorSquRoller", "CorSquRoller"),
        ("BillingNote", "BillingNote"),
        ("ProductNote", "ProductNote"),
        ("CustomerNote", "CustomerNote"),
        ("KHTSYQ", "KHTSYQ"),
        ("Remarks", "Remarks"),
    ]
    parts = []
    for label, key in fields:
        value = clean_text(row.get(key), 500)
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts)


def unique_order_no(row: dict[str, str], duplicate_bill_ids: set[str]) -> str:
    bill_id = clean_text(row.get("BillID"), 64)
    legacy_id = clean_text(row.get("ID"), 32)
    if bill_id and bill_id not in duplicate_bill_ids:
        return bill_id
    if bill_id and legacy_id:
        return f"{bill_id}-{legacy_id}"
    if legacy_id:
        return f"LEG-BILL-{legacy_id}"
    return "LEG-BILL-MISSING"


def import_bills_tsv(
    db: Session,
    path: Path,
    apply: bool,
    status: str,
    include_deleted: bool,
) -> dict[str, Any]:
    rows = read_bills_tsv(path)
    bill_rows = [row for row in rows if include_deleted or not truthy_int(row.get("Deleted"))]
    bill_ids = [clean_text(row.get("BillID"), 64) for row in bill_rows]
    duplicate_bill_ids = {bill_id for bill_id, count in Counter(bill_id for bill_id in bill_ids if bill_id).items() if count > 1}

    stats: dict[str, Any] = {
        "source_file": str(path),
        "rows": len(rows),
        "bill_rows": len(bill_rows),
        "duplicate_bill_ids": len(duplicate_bill_ids),
        "orders_created": 0,
        "orders_updated": 0,
        "orders_skipped_missing_customer": 0,
        "orders_skipped_missing_order_no": 0,
        "missing_customer_ids": [],
        "total_amount": 0.0,
        "dry_run": not apply,
    }

    customer_cache: dict[str, Customer | None] = {}

    for row in bill_rows:
        order_no = unique_order_no(row, duplicate_bill_ids)
        if order_no == "LEG-BILL-MISSING":
            stats["orders_skipped_missing_order_no"] += 1
            continue

        legacy_company_id = clean_text(row.get("CompanyID"), 32)
        customer = customer_cache.get(legacy_company_id)
        if legacy_company_id not in customer_cache:
            customer = (
                db.query(Customer)
                .filter(Customer.legacy_company_id == legacy_company_id, Customer.deleted_at.is_(None))
                .first()
            )
            customer_cache[legacy_company_id] = customer
        if customer is None:
            stats["orders_skipped_missing_customer"] += 1
            if legacy_company_id:
                stats["missing_customer_ids"].append(legacy_company_id)
            continue

        order_date = parse_date(row.get("DateBill")) or parse_date(row.get("CreateTime")) or date.today()
        due_date = parse_date(row.get("DeliveryTime")) or parse_date(row.get("DeliTime")) or order_date
        amount = positive_decimal(row.get("JsTotal"), row.get("Total"), row.get("PPrice"), row.get("ZPrice"))
        quantity = quantity_from_row(row)
        stats["total_amount"] += float(amount)

        item_values = {
            "product_id": None,
            "product_name": clean_text(row.get("ProductName"), 128) or order_no,
            "specification": specification_from_row(row),
            "quantity": quantity,
            "unit": "pcs",
            "unit_price": unit_price(amount, quantity),
            "amount": amount,
            "route_id": None,
            "remark": compact_parts(
                [
                    f"Plan={clean_text(row.get('ProductPlanID'), 80)}" if clean_text(row.get("ProductPlanID")) else None,
                    f"PS={clean_text(row.get('PS'), 80)}" if clean_text(row.get("PS")) else None,
                    f"PAW={clean_text(row.get('PAW'), 80)}" if clean_text(row.get("PAW")) else None,
                ]
            ),
        }
        order_values = {
            "legacy_bussiness_mst_id": clean_text(row.get("ID"), 32),
            "legacy_bussiness_mst_rid": clean_text(row.get("RID"), 32),
            "customer_id": customer.id,
            "product_summary": item_values["product_name"],
            "order_date": order_date,
            "due_date": due_date,
            "total_amount": amount,
            "status": "cancelled" if truthy_int(row.get("Deleted")) else status,
            "priority": "normal",
            "route_id": None,
            "remark": remark_from_row(row),
        }

        order = (
            db.query(SalesOrder)
            .options(selectinload(SalesOrder.items))
            .filter(SalesOrder.order_no == order_no, SalesOrder.deleted_at.is_(None))
            .first()
        )
        if order is None:
            stats["orders_created"] += 1
            if apply:
                order = SalesOrder(order_no=order_no, **order_values)
                order.items.append(SalesOrderItem(**item_values))
                db.add(order)
        else:
            stats["orders_updated"] += 1
            if apply:
                for field, value in order_values.items():
                    setattr(order, field, value)
                if order.items:
                    item = order.items[0]
                    for field, value in item_values.items():
                        setattr(item, field, value)
                else:
                    order.items.append(SalesOrderItem(**item_values))

    stats["missing_customer_ids"] = sorted(set(stats["missing_customer_ids"]))[:50]
    stats["total_amount"] = round(stats["total_amount"], 2)
    if apply:
        db.commit()
    else:
        db.rollback()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Import legacy B_BussinessMst TSV export as archived sales orders.")
    parser.add_argument("--file", required=True, type=Path, help="Path to B_BussinessMst_clean.tsv.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Omit for dry-run.")
    parser.add_argument("--status", default="archived", help="Status for imported non-deleted orders.")
    parser.add_argument("--include-deleted", action="store_true", help="Import deleted legacy bills as cancelled orders.")
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = import_bills_tsv(
            db=db,
            path=args.file,
            apply=args.apply,
            status=args.status,
            include_deleted=args.include_deleted,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
