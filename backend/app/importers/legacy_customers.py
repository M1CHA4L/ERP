from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.importers.legacy_excel import read_raw_biff_table
from app.models.customer import Customer
from app.models.finance import Payment, Receivable
from app.models.rbac import Role, User


CUSTOMER_FILE_HEADERS = {
    "payment_method": "结款方式",
    "name": "客户全称",
    "code": "客户简称",
    "customer_type": "客户类型",
    "is_key_customer": "重点客户",
    "opening_balance": "结欠余额",
    "address": "地址",
    "salesperson": "业务员",
    "company_phone": "公司电话",
    "fax": "传真",
    "phone": "客户联系电话",
    "contact_name": "联系人",
    "office": "办事处",
    "opening_remark": "期初备注",
    "bank_name": "开户银行",
    "bank_account": "开户账号",
    "tax_no": "税号",
    "delivery_method": "交货方式",
    "copper_thickness": "镀铜厚度",
    "chrome_time": "镀铬时间",
    "stripping_cost": "退镀成本",
    "reconciliation_cycle": "对账日期从",
    "reconciliation_day": "几号",
    "remark": "备注",
}

LEGACY_SALESPERSON_USERNAME_ALIASES = {
    "管理员": "admin",
    "锟斤拷锟斤拷员": "admin",
    "administrator": "admin",
}


def clean_text(value: Any, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if not text:
        return None
    if max_length and len(text) > max_length:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
        text = f"{text[: max_length - 9]}-{digest}"
    return text


def normalize_customer_code(value: Any) -> str | None:
    return clean_text(value, 64)


def normalize_bool(value: Any) -> bool:
    text = clean_text(value)
    if text is None:
        return False
    return text.lower() in {"1", "true", "yes", "y", "是", "重点", "checked"}


def to_decimal(value: Any) -> Decimal | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def to_int(value: Any) -> int | None:
    number = to_decimal(value)
    if number is None:
        return None
    return int(number)


def payment_terms_to_days(value: Any) -> int:
    text = (clean_text(value) or "").lower().replace(" ", "")
    if not text or "cash" in text:
        return 0
    days_match = re.search(r"(\d+)days?", text)
    if days_match:
        return int(days_match.group(1))
    month_count_match = re.search(r"(\d+)(?:mothly|monthly|month)", text)
    if month_count_match:
        return int(month_count_match.group(1)) * 30
    if any(word in text for word in ("mothly", "monthly", "month")):
        return 30
    return 30


def salesperson_lookup_key(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def username_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text).strip("_").lower()
    return slug or "sales"


def existing_user_by_name(db: Session, name: str) -> User | None:
    lowered = salesperson_lookup_key(name)
    alias_username = LEGACY_SALESPERSON_USERNAME_ALIASES.get(lowered)
    if alias_username is None and ("锟" in lowered or "�" in lowered):
        alias_username = "admin"
    if alias_username:
        alias_user = db.query(User).filter(User.username == alias_username, User.deleted_at.is_(None)).first()
        if alias_user:
            return alias_user
    return (
        db.query(User)
        .filter(
            User.deleted_at.is_(None),
            func.lower(User.real_name) == lowered,
        )
        .first()
        or db.query(User)
        .filter(
            User.deleted_at.is_(None),
            func.lower(User.username) == lowered,
        )
        .first()
    )


def create_salesperson(db: Session, name: str, default_password: str) -> User:
    base_username = f"legacy_{username_slug(name)}"[:56]
    username = base_username
    index = 2
    while db.query(User).filter(User.username == username).first():
        suffix = f"_{index}"
        username = f"{base_username[: 64 - len(suffix)]}{suffix}"
        index += 1

    user = User(
        username=username,
        password_hash=get_password_hash(default_password),
        real_name=name,
        department="Sales",
        status="active",
    )
    sales_role = db.query(Role).filter(Role.code == "sales", Role.status == "active").first()
    if sales_role:
        user.roles.append(sales_role)
    db.add(user)
    db.flush()
    return user


def find_or_create_salesperson(
    db: Session,
    name: str | None,
    create_missing: bool,
    default_password: str,
    cache: dict[str, tuple[User | None, bool]],
) -> tuple[User | None, bool]:
    if not name:
        return None, False
    key = salesperson_lookup_key(name)
    if key in cache:
        user, _created = cache[key]
        return user, False
    user = existing_user_by_name(db, name)
    created = False
    if user is None and create_missing:
        user = create_salesperson(db, name, default_password)
        created = True
    cache[key] = (user, created)
    return user, created


def build_customer_values(row: dict[str, Any], salesperson: User | None) -> dict[str, Any]:
    primary_phone = clean_text(row.get(CUSTOMER_FILE_HEADERS["phone"]), 32)
    company_phone = clean_text(row.get(CUSTOMER_FILE_HEADERS["company_phone"]), 32)
    return {
        "name": clean_text(row.get(CUSTOMER_FILE_HEADERS["name"]), 128)
        or clean_text(row.get(CUSTOMER_FILE_HEADERS["code"]), 128),
        "customer_type": clean_text(row.get(CUSTOMER_FILE_HEADERS["customer_type"]), 32),
        "is_key_customer": normalize_bool(row.get(CUSTOMER_FILE_HEADERS["is_key_customer"])),
        "contact_name": clean_text(row.get(CUSTOMER_FILE_HEADERS["contact_name"]), 64),
        "phone": primary_phone or company_phone,
        "company_phone": company_phone,
        "fax": clean_text(row.get(CUSTOMER_FILE_HEADERS["fax"]), 32),
        "address": clean_text(row.get(CUSTOMER_FILE_HEADERS["address"]), 255),
        "salesperson_id": salesperson.id if salesperson else None,
        "payment_terms_days": payment_terms_to_days(row.get(CUSTOMER_FILE_HEADERS["payment_method"])),
        "tax_no": clean_text(row.get(CUSTOMER_FILE_HEADERS["tax_no"]), 64),
        "office": clean_text(row.get(CUSTOMER_FILE_HEADERS["office"]), 64),
        "opening_remark": clean_text(row.get(CUSTOMER_FILE_HEADERS["opening_remark"])),
        "bank_name": clean_text(row.get(CUSTOMER_FILE_HEADERS["bank_name"]), 128),
        "bank_account": clean_text(row.get(CUSTOMER_FILE_HEADERS["bank_account"]), 128),
        "delivery_method": clean_text(row.get(CUSTOMER_FILE_HEADERS["delivery_method"]), 64),
        "copper_thickness": to_decimal(row.get(CUSTOMER_FILE_HEADERS["copper_thickness"])),
        "chrome_time": to_decimal(row.get(CUSTOMER_FILE_HEADERS["chrome_time"])),
        "stripping_cost": to_decimal(row.get(CUSTOMER_FILE_HEADERS["stripping_cost"])),
        "reconciliation_cycle": clean_text(row.get(CUSTOMER_FILE_HEADERS["reconciliation_cycle"]), 32),
        "reconciliation_day": to_int(row.get(CUSTOMER_FILE_HEADERS["reconciliation_day"])),
        "remark": clean_text(row.get(CUSTOMER_FILE_HEADERS["remark"])),
        "status": "active",
    }


def upsert_opening_receivable(db: Session, customer: Customer, amount: Decimal) -> str:
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
        receivable = Receivable(
            receivable_no=f"OPEN-{customer.customer_code}"[:64],
            sales_order_id=None,
            delivery_order_id=None,
            customer_id=customer.id,
            amount=amount,
            received_amount=Decimal("0"),
            balance_amount=amount,
            due_date=date.today(),
            source_type="opening_balance",
            invoice_status="pending",
            finance_status="pending_invoice",
            status="active",
            remark="Legacy opening balance",
        )
        db.add(receivable)
        return "created"

    has_payments = db.query(Payment).filter(Payment.receivable_id == existing.id, Payment.deleted_at.is_(None)).first()
    if has_payments:
        return "skipped_has_payment"
    existing.amount = amount
    existing.received_amount = Decimal("0")
    existing.balance_amount = amount
    existing.due_date = date.today()
    existing.status = "active"
    existing.finance_status = "pending_invoice"
    return "updated"


def import_customers(
    db: Session,
    path: Path,
    apply: bool,
    create_missing_salespeople: bool,
    default_sales_password: str,
    limit: int | None = None,
) -> dict[str, Any]:
    rows = read_raw_biff_table(path)
    if limit:
        rows = rows[:limit]

    codes = [normalize_customer_code(row.get(CUSTOMER_FILE_HEADERS["code"])) for row in rows]
    duplicate_codes = sorted(code for code, count in Counter(code for code in codes if code).items() if count > 1)
    if duplicate_codes:
        raise ValueError(f"Duplicate customer short names after normalization: {duplicate_codes[:20]}")

    stats: dict[str, Any] = {
        "source_file": str(path),
        "rows": len(rows),
        "customers_created": 0,
        "customers_updated": 0,
        "customers_skipped_missing_code": 0,
        "opening_receivables_created": 0,
        "opening_receivables_updated": 0,
        "opening_receivables_skipped_has_payment": 0,
        "opening_receivables_total": 0.0,
        "salespeople_created": 0,
        "salespeople_matched": 0,
        "salespeople_unmatched": [],
        "dry_run": not apply,
    }
    salesperson_cache: dict[str, tuple[User | None, bool]] = {}

    for row in rows:
        customer_code = normalize_customer_code(row.get(CUSTOMER_FILE_HEADERS["code"]))
        if not customer_code:
            stats["customers_skipped_missing_code"] += 1
            continue

        salesperson_name = clean_text(row.get(CUSTOMER_FILE_HEADERS["salesperson"]), 64)
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

        values = build_customer_values(row, salesperson)
        customer = db.query(Customer).filter(Customer.customer_code == customer_code).first()
        if customer is None:
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

        opening_balance = to_decimal(row.get(CUSTOMER_FILE_HEADERS["opening_balance"])) or Decimal("0")
        if opening_balance > 0:
            stats["opening_receivables_total"] += float(opening_balance)
            if apply and customer is not None:
                result = upsert_opening_receivable(db, customer, opening_balance)
                key = f"opening_receivables_{result}"
                stats[key] += 1

    stats["salespeople_unmatched"] = sorted(set(stats["salespeople_unmatched"]))
    if not apply:
        db.rollback()
    else:
        db.commit()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Import legacy ERP customer raw BIFF .xls export.")
    parser.add_argument("--file", required=True, type=Path, help="Path to legacy customer .xls export.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Omit for dry-run.")
    parser.add_argument("--create-missing-salespeople", action="store_true", help="Create missing sales users during apply.")
    parser.add_argument("--default-sales-password", default="import123", help="Password for auto-created sales users.")
    parser.add_argument("--limit", type=int, default=None, help="Import only the first N rows.")
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = import_customers(
            db,
            args.file,
            apply=args.apply,
            create_missing_salespeople=args.create_missing_salespeople,
            default_sales_password=args.default_sales_password,
            limit=args.limit,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
