from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.db import base  # noqa: F401
from app.db.session import SessionLocal
from app.importers.legacy_bills_tsv import compact_parts, parse_date
from app.importers.legacy_company_tsv import truthy_int
from app.importers.legacy_customers import clean_text, to_decimal
from app.models.logistics import DeliveryOrder, DeliveryOrderItem
from app.models.sales import SalesOrder

csv.field_size_limit(sys.maxsize)


ORDER_MST_HEADERS = [
    "ID",
    "RID",
    "CompanyID",
    "DateBill",
    "BillID",
    "ProductNote",
    "DeliveryTime",
    "State",
    "ExTime",
    "Exer",
    "Remarks",
    "InOutPut",
    "AddSub",
    "DeptID",
    "JSR",
    "FKFS",
    "YSDH",
    "StockID",
    "BillType",
    "BillingNote",
    "OrderID",
    "FHTotal",
    "FHNumber",
    "verify",
    "Proposition",
    "Total",
    "ActualTotal",
    "DiscountTotal",
    "AccountWays",
    "BussinessMstID",
    "SKLX",
    "CreateTime",
    "UpdateTime",
    "Deleted",
]

ORDER_DTL_HEADERS = [
    "ID",
    "RID",
    "Number",
    "Price",
    "Total",
    "Unit",
    "ProductID",
    "OrderID",
    "DeliveryTime",
    "copies",
    "Remarks",
    "CalcWay",
    "Squre",
    "Length",
    "Weight",
    "CustomerID",
    "Specif",
    "FullName",
    "MaterialID",
    "State",
    "AddSub",
    "InOutPut",
    "InNumber",
    "CustomerName",
    "FHTotal",
    "YHTotal",
    "FHNumber",
    "YHNumber",
    "SignTime",
    "SignName",
    "SHBillID",
    "YFNumber",
    "YFTotal",
    "Width",
    "Thin",
    "Diameter",
    "BussinessMstID",
    "JHRID",
    "DHNumber",
    "CreateTime",
    "UpdateTime",
    "Deleted",
]


def read_legacy_tsv(path: Path, headers: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="gb18030", errors="replace", newline="") as file:
        raw_rows = list(csv.reader(file, delimiter="\t"))
    rows: list[dict[str, str]] = []
    for row in raw_rows:
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


def parse_datetime(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    candidates = [
        text,
        text[:19],
        text[:10],
        text.replace("/", "-")[:19],
        text.replace("/", "-")[:10],
    ]
    for candidate in candidates:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    parsed_date = parse_date(text)
    if parsed_date:
        return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=timezone.utc)
    return None


def first_positive_decimal(*values: Any, fallback: Decimal = Decimal("1")) -> Decimal:
    for value in values:
        amount = to_decimal(value)
        if amount and amount > 0:
            return amount
    return fallback


def build_delivery_no(row: dict[str, str], duplicate_bill_ids: set[str]) -> str:
    bill_id = clean_text(row.get("BillID"), 64)
    rid = clean_text(row.get("RID"), 32)
    if bill_id and bill_id not in duplicate_bill_ids:
        return bill_id
    if bill_id and rid:
        return f"{bill_id}-{rid}"
    if rid:
        return f"LEG-DO-{rid}"
    return "LEG-DO-MISSING"


def delivery_remark(row: dict[str, str]) -> str:
    fields = [
        ("Legacy B_OrderMst.ID", "ID"),
        ("Legacy B_OrderMst.RID", "RID"),
        ("Legacy BillID", "BillID"),
        ("Legacy BillType", "BillType"),
        ("Legacy BussinessMstID", "BussinessMstID"),
        ("JSR", "JSR"),
        ("FKFS", "FKFS"),
        ("YSDH", "YSDH"),
        ("BillingNote", "BillingNote"),
        ("ProductNote", "ProductNote"),
        ("Proposition", "Proposition"),
        ("Remarks", "Remarks"),
    ]
    parts = []
    for label, key in fields:
        value = clean_text(row.get(key), 500)
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts)


def choose_delivery_rows(rows: list[dict[str, str]], bill_type: str | None) -> tuple[list[dict[str, str]], str | None]:
    active_rows = [
        row
        for row in rows
        if not truthy_int(row.get("Deleted"))
        and clean_text(row.get("BussinessMstID"))
        and clean_text(row.get("BussinessMstID")) != "0"
    ]
    if bill_type:
        return [row for row in active_rows if clean_text(row.get("BillType")) == bill_type], bill_type

    bill_type_counts = Counter(clean_text(row.get("BillType")) for row in active_rows if clean_text(row.get("BillType")))
    selected_bill_type = bill_type_counts.most_common(1)[0][0] if bill_type_counts else None
    if selected_bill_type is None:
        return active_rows, None
    return [row for row in active_rows if clean_text(row.get("BillType")) == selected_bill_type], selected_bill_type


def import_deliveries_tsv(
    db: Session,
    order_mst_file: Path,
    order_dtl_file: Path | None,
    apply: bool,
    bill_type: str | None,
) -> dict[str, Any]:
    mst_rows = read_legacy_tsv(order_mst_file, ORDER_MST_HEADERS)
    dtl_rows = read_legacy_tsv(order_dtl_file, ORDER_DTL_HEADERS) if order_dtl_file else []
    delivery_rows, selected_bill_type = choose_delivery_rows(mst_rows, bill_type)
    duplicate_bill_ids = {
        bill_id
        for bill_id, count in Counter(clean_text(row.get("BillID"), 64) for row in delivery_rows if clean_text(row.get("BillID"))).items()
        if count > 1
    }

    stats: dict[str, Any] = {
        "order_mst_file": str(order_mst_file),
        "order_dtl_file": str(order_dtl_file) if order_dtl_file else None,
        "order_mst_rows": len(mst_rows),
        "order_dtl_rows": len(dtl_rows),
        "selected_bill_type": selected_bill_type,
        "delivery_source_rows": len(delivery_rows),
        "duplicate_delivery_bill_ids": len(duplicate_bill_ids),
        "deliveries_created": 0,
        "deliveries_updated": 0,
        "deliveries_skipped_missing_sales_order": 0,
        "deliveries_skipped_missing_delivery_no": 0,
        "missing_bussiness_mst_rids": [],
        "dry_run": not apply,
    }

    order_cache: dict[str, SalesOrder | None] = {}
    for row in delivery_rows:
        legacy_rid = clean_text(row.get("BussinessMstID"), 32)
        sales_order = order_cache.get(legacy_rid)
        if legacy_rid not in order_cache:
            sales_order = (
                db.query(SalesOrder)
                .options(selectinload(SalesOrder.items))
                .filter(SalesOrder.legacy_bussiness_mst_rid == legacy_rid, SalesOrder.deleted_at.is_(None))
                .first()
            )
            order_cache[legacy_rid] = sales_order
        if sales_order is None:
            stats["deliveries_skipped_missing_sales_order"] += 1
            stats["missing_bussiness_mst_rids"].append(legacy_rid)
            continue

        delivery_no = build_delivery_no(row, duplicate_bill_ids)
        if delivery_no == "LEG-DO-MISSING":
            stats["deliveries_skipped_missing_delivery_no"] += 1
            continue

        delivery_time = (
            parse_datetime(row.get("DateBill"))
            or parse_datetime(row.get("DeliveryTime"))
            or parse_datetime(row.get("CreateTime"))
            or datetime.now(timezone.utc)
        )
        signed_at = parse_datetime(row.get("ExTime")) or delivery_time
        first_item = sales_order.items[0] if sales_order.items else None
        product_name = first_item.product_name if first_item else sales_order.product_summary
        specification = first_item.specification if first_item else None
        quantity = first_positive_decimal(row.get("FHNumber"), row.get("FHTotal"), fallback=Decimal("1"))
        unit = first_item.unit if first_item else "pcs"

        delivery_values = {
            "delivery_no": delivery_no,
            "legacy_order_mst_id": clean_text(row.get("ID"), 32),
            "legacy_order_mst_rid": clean_text(row.get("RID"), 32),
            "legacy_bill_type": clean_text(row.get("BillType"), 64),
            "sales_order_id": sales_order.id,
            "customer_id": sales_order.customer_id,
            "address": "",
            "delivery_time": delivery_time,
            "driver_name": clean_text(row.get("JSR"), 64) or clean_text(row.get("Exer"), 64),
            "logistics_no": clean_text(row.get("YSDH"), 128) or clean_text(row.get("BillID"), 128),
            "status": "signed",
            "signed_by": clean_text(row.get("Exer"), 64) or clean_text(row.get("JSR"), 64),
            "signed_at": signed_at,
            "remark": delivery_remark(row),
        }
        item_values = {
            "sales_order_item_id": first_item.id if first_item else None,
            "product_name": product_name,
            "specification": specification,
            "quantity": quantity,
            "unit": unit,
        }

        delivery = (
            db.query(DeliveryOrder)
            .options(selectinload(DeliveryOrder.items))
            .filter(DeliveryOrder.legacy_order_mst_rid == delivery_values["legacy_order_mst_rid"], DeliveryOrder.deleted_at.is_(None))
            .first()
        )
        if delivery is None:
            delivery = db.query(DeliveryOrder).options(selectinload(DeliveryOrder.items)).filter(DeliveryOrder.delivery_no == delivery_no).first()

        if delivery is None:
            stats["deliveries_created"] += 1
            if apply:
                delivery = DeliveryOrder(**delivery_values)
                delivery.items.append(DeliveryOrderItem(**item_values))
                db.add(delivery)
        else:
            stats["deliveries_updated"] += 1
            if apply:
                for field, value in delivery_values.items():
                    setattr(delivery, field, value)
                if delivery.items:
                    item = delivery.items[0]
                    for field, value in item_values.items():
                        setattr(item, field, value)
                else:
                    delivery.items.append(DeliveryOrderItem(**item_values))

    stats["missing_bussiness_mst_rids"] = sorted(set(stats["missing_bussiness_mst_rids"]))[:50]
    if apply:
        db.commit()
    else:
        db.rollback()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Import legacy B_OrderMst delivery rows.")
    parser.add_argument("--order-mst-file", required=True, type=Path)
    parser.add_argument("--order-dtl-file", type=Path)
    parser.add_argument("--bill-type", help="Legacy BillType to import. Omit to use the most frequent linked type.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Omit for dry-run.")
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = import_deliveries_tsv(
            db=db,
            order_mst_file=args.order_mst_file,
            order_dtl_file=args.order_dtl_file,
            apply=args.apply,
            bill_type=args.bill_type,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
