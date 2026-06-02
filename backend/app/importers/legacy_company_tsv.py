from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db import base  # noqa: F401
from app.db.session import SessionLocal
from app.importers.legacy_customers import (
    clean_text,
    find_or_create_salesperson,
    normalize_customer_code,
    payment_terms_to_days,
    to_decimal,
    upsert_opening_receivable,
)
from app.models.customer import Customer
from app.models.finance import Payment, Receivable
from app.models.rbac import User


COMPANY_HEADERS_WITH_RID = [
    "ID",
    "RID",
    "FullName",
    "SimpleName",
    "IsCus",
    "IsSup",
    "IsClass",
    "Deleted",
    "IsStop",
    "SaleMan",
    "Contact",
    "ContactPhone",
    "MbPhone",
    "Address",
    "BeMoney",
    "CopperTime",
    "CopperThick",
    "JKFS",
]

COMPANY_HEADERS_WITHOUT_RID = [header for header in COMPANY_HEADERS_WITH_RID if header != "RID"]


def read_sqlcmd_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as file:
        rows = list(csv.reader(file, delimiter="\t"))
    if not rows:
        return []

    headers = [header.strip() for header in rows[0]]
    items: list[dict[str, str]] = []
    for row in rows[1:]:
        if not row:
            continue
        first_cell = row[0].strip()
        if first_cell.startswith("--") or first_cell.startswith("("):
            continue
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        values = {headers[index]: row[index].strip() for index in range(len(headers))}
        if any(values.values()):
            items.append(values)
    return items


def read_company_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as file:
        raw_rows = list(csv.reader(file, delimiter="\t"))
    if not raw_rows:
        return []

    first_row = [cell.strip() for cell in raw_rows[0]]
    has_header = "FullName" in first_row and "SimpleName" in first_row
    if has_header:
        headers = first_row
        data_rows = raw_rows[1:]
    elif len(first_row) == len(COMPANY_HEADERS_WITH_RID):
        headers = COMPANY_HEADERS_WITH_RID
        data_rows = raw_rows
    else:
        headers = COMPANY_HEADERS_WITHOUT_RID
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


def truthy_int(value: Any) -> bool:
    text = clean_text(value)
    return text in {"1", "true", "True", "TRUE", "是"}


def customer_values_from_company_row(row: dict[str, str], salesperson: User | None) -> dict[str, Any]:
    contact_phone = clean_text(row.get("ContactPhone"), 32)
    mobile_phone = clean_text(row.get("MbPhone"), 32)
    jkfs = clean_text(row.get("JKFS"), 64)
    remark = clean_text(row.get("Remarks"))
    payment_note = f"Legacy JKFS: {jkfs}" if jkfs else None
    if remark and payment_note:
        remark = f"{remark}\n{payment_note}"
    elif payment_note:
        remark = payment_note

    return {
        "legacy_company_id": clean_text(row.get("RID"), 32) or clean_text(row.get("ID"), 32),
        "name": clean_text(row.get("FullName"), 128) or clean_text(row.get("SimpleName"), 128),
        "contact_name": clean_text(row.get("Contact"), 64),
        "phone": contact_phone or mobile_phone,
        "address": clean_text(row.get("Address"), 255),
        "salesperson_id": salesperson.id if salesperson else None,
        "payment_terms_days": payment_terms_to_days(jkfs),
        "copper_thickness": to_decimal(row.get("CopperThick")),
        "chrome_time": to_decimal(row.get("CopperTime")),
        "opening_remark": (
            f"Legacy D_Company.ID={clean_text(row.get('ID'))}"
            + (f"; RID={clean_text(row.get('RID'))}" if clean_text(row.get("RID")) else "")
        ),
        "remark": remark,
        "status": "disabled" if truthy_int(row.get("IsStop")) else "active",
    }


def void_opening_receivable_if_needed(db: Session, customer: Customer) -> str | None:
    existing = (
        db.query(Receivable)
        .filter(
            Receivable.customer_id == customer.id,
            Receivable.source_type == "opening_balance",
            Receivable.deleted_at.is_(None),
        )
        .first()
    )
    if existing is None:
        return None
    has_payments = db.query(Payment).filter(Payment.receivable_id == existing.id, Payment.deleted_at.is_(None)).first()
    if has_payments:
        return "skipped_has_payment"
    existing.amount = Decimal("0")
    existing.received_amount = Decimal("0")
    existing.balance_amount = Decimal("0")
    existing.status = "cancelled"
    existing.finance_status = "cancelled"
    existing.remark = "Legacy opening balance cleared because source BeMoney is not positive"
    return "cancelled"


def import_company_tsv(
    db: Session,
    path: Path,
    apply: bool,
    create_missing_salespeople: bool,
    default_sales_password: str,
    create_missing_customers: bool,
) -> dict[str, Any]:
    rows = read_company_tsv(path)
    customer_rows = [
        row
        for row in rows
        if truthy_int(row.get("IsCus")) and not truthy_int(row.get("Deleted")) and not truthy_int(row.get("IsClass"))
    ]

    codes = [
        normalize_customer_code(row.get("SimpleName")) or normalize_customer_code(row.get("FullName"))
        for row in customer_rows
    ]
    duplicate_codes = sorted(code for code, count in Counter(code for code in codes if code).items() if count > 1)
    stats: dict[str, Any] = {
        "source_file": str(path),
        "rows": len(rows),
        "customer_rows": len(customer_rows),
        "customers_created": 0,
        "customers_updated": 0,
        "customers_skipped_missing_code": 0,
        "customers_skipped_missing_existing": 0,
        "duplicate_customer_codes_disambiguated": len(duplicate_codes),
        "salespeople_created": 0,
        "salespeople_matched": 0,
        "salespeople_unmatched": [],
        "opening_receivables_created": 0,
        "opening_receivables_updated": 0,
        "opening_receivables_cancelled": 0,
        "opening_receivables_skipped_has_payment": 0,
        "positive_opening_balance_count": 0,
        "positive_opening_balance_total": 0.0,
        "negative_balance_count": 0,
        "negative_balance_total": 0.0,
        "dry_run": not apply,
    }
    salesperson_cache: dict[str, tuple[User | None, bool]] = {}

    for row in customer_rows:
        base_customer_code = normalize_customer_code(row.get("SimpleName")) or normalize_customer_code(row.get("FullName"))
        legacy_id = clean_text(row.get("ID"), 20)
        customer_code = base_customer_code
        if base_customer_code in duplicate_codes and legacy_id:
            customer_code = normalize_customer_code(f"{base_customer_code}-{legacy_id}")
        if not customer_code:
            stats["customers_skipped_missing_code"] += 1
            continue

        salesperson_name = clean_text(row.get("SaleMan"), 64)
        salesperson, salesperson_created = find_or_create_salesperson(
            db,
            salesperson_name,
            create_missing_salespeople and apply,
            default_sales_password,
            salesperson_cache,
        )
        if salesperson_name and salesperson is None:
            stats["salespeople_unmatched"].append(salesperson_name)
        elif salesperson_name and salesperson_created:
            stats["salespeople_created"] += 1
        elif salesperson_name:
            stats["salespeople_matched"] += 1

        values = customer_values_from_company_row(row, salesperson)
        customer = db.query(Customer).filter(Customer.customer_code == customer_code).first()
        if customer is None:
            if not create_missing_customers:
                stats["customers_skipped_missing_existing"] += 1
                continue
            stats["customers_created"] += 1
            if apply:
                customer = Customer(customer_code=customer_code, **values)
                db.add(customer)
                db.flush()
        else:
            stats["customers_updated"] += 1
            if apply:
                for field, value in values.items():
                    setattr(customer, field, value)
                db.flush()

        balance = to_decimal(row.get("BeMoney")) or Decimal("0")
        if balance > 0:
            stats["positive_opening_balance_count"] += 1
            stats["positive_opening_balance_total"] += float(balance)
            if apply and customer is not None:
                result = upsert_opening_receivable(db, customer, balance)
                stats[f"opening_receivables_{result}"] += 1
        elif balance < 0:
            stats["negative_balance_count"] += 1
            stats["negative_balance_total"] += float(balance)
            if apply and customer is not None:
                result = void_opening_receivable_if_needed(db, customer)
                if result:
                    stats[f"opening_receivables_{result}"] += 1

    stats["salespeople_unmatched"] = sorted(set(stats["salespeople_unmatched"]))
    stats["positive_opening_balance_total"] = round(stats["positive_opening_balance_total"], 2)
    stats["negative_balance_total"] = round(stats["negative_balance_total"], 2)
    if apply:
        db.commit()
    else:
        db.rollback()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Supplement customers from legacy D_Company TSV export.")
    parser.add_argument("--file", required=True, type=Path, help="Path to D_Company_clean.tsv.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Omit for dry-run.")
    parser.add_argument("--create-missing-salespeople", action="store_true")
    parser.add_argument("--create-missing-customers", action="store_true")
    parser.add_argument("--default-sales-password", default="import123")
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = import_company_tsv(
            db=db,
            path=args.file,
            apply=args.apply,
            create_missing_salespeople=args.create_missing_salespeople,
            default_sales_password=args.default_sales_password,
            create_missing_customers=args.create_missing_customers,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
