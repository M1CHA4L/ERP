from __future__ import annotations

import re
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.rbac import User
from app.models.sales import PlateNumberReservation, SalesOrder

PLATE_PREFIX_BY_KIND = {
    "normal": "S",
    "ppl": "P",
    "special": "B",
}

DERIVATION_SUFFIX_BY_TYPE = {
    "revision": "C",
    "remake": "R",
    "internal_rework": "IR",
    "external_rework": "OR",
}

ORDER_PLATE_FIELDS = ("cylinder_id", "no", "sample_no", "original_no")


def normalize_plate_number(value: object) -> str:
    return str(value or "").strip().upper()


def normalize_plate_number_kind(value: object) -> str:
    kind = str(value or "normal").strip().lower()
    if kind not in PLATE_PREFIX_BY_KIND:
        raise ValueError("Invalid plate number type.")
    return kind


def normalize_derivation_type(value: object, *, default: str = "revision") -> str:
    derivation_type = str(value or default).strip().lower()
    if derivation_type not in DERIVATION_SUFFIX_BY_TYPE:
        raise ValueError("Invalid plate number derivation type.")
    return derivation_type


def primary_plate_number_from_details(details: dict | None) -> str:
    details = details or {}
    for field in ORDER_PLATE_FIELDS:
        plate_no = normalize_plate_number(details.get(field))
        if plate_no:
            return plate_no
    return ""


def primary_plate_number_from_order(order: SalesOrder) -> str:
    return primary_plate_number_from_details(order.plate_details) or normalize_plate_number(order.order_no)


def _lock_key(db: Session, key: str) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})


def _order_plate_candidates(db: Session, pattern: str) -> list[str]:
    selects = [
        f"SELECT plate_details ->> '{field}' AS plate_no FROM sales_orders WHERE deleted_at IS NULL"
        for field in ORDER_PLATE_FIELDS
    ]
    selects.append("SELECT order_no AS plate_no FROM sales_orders WHERE deleted_at IS NULL")
    rows = db.execute(
        text(
            f"""
            SELECT plate_no
            FROM ({' UNION ALL '.join(selects)}) AS plate_values
            WHERE plate_no IS NOT NULL
              AND upper(plate_no) LIKE :pattern
            """
        ),
        {"pattern": pattern.upper()},
    ).scalars()
    return [normalize_plate_number(value) for value in rows]


def _max_direct_sequence(db: Session, prefix: str, year_month: str) -> int:
    table_max = (
        db.query(func.max(PlateNumberReservation.sequence_no))
        .filter(
            PlateNumberReservation.prefix == prefix,
            PlateNumberReservation.year_month == year_month,
        )
        .scalar()
        or 0
    )
    matcher = re.compile(rf"^{re.escape(prefix)}{year_month}(\d+)$")
    order_max = 0
    for value in _order_plate_candidates(db, f"{prefix}{year_month}%"):
        match = matcher.match(value)
        if match:
            order_max = max(order_max, int(match.group(1)))
    return max(int(table_max), order_max)


def reserve_plate_numbers(
    db: Session,
    *,
    user: User,
    plate_number_kind: str,
    count: int,
) -> list[PlateNumberReservation]:
    kind = normalize_plate_number_kind(plate_number_kind)
    if count < 1 or count > 50:
        raise ValueError("Plate number request count must be between 1 and 50.")

    prefix = PLATE_PREFIX_BY_KIND[kind]
    year_month = date.today().strftime("%Y%m")
    _lock_key(db, f"plate-number:{prefix}:{year_month}")

    reservations: list[PlateNumberReservation] = []
    reusable = (
        db.query(PlateNumberReservation)
        .filter(
            PlateNumberReservation.deleted_at.is_(None),
            PlateNumberReservation.prefix == prefix,
            PlateNumberReservation.year_month == year_month,
            PlateNumberReservation.status == "available",
            PlateNumberReservation.assigned_user_id.is_(None),
        )
        .order_by(PlateNumberReservation.sequence_no.asc())
        .limit(count)
        .all()
    )
    for reservation in reusable:
        reservation.status = "reserved"
        reservation.assigned_user_id = user.id
        reservation.returned_at = None
        reservation.updated_by = user.id
        reservations.append(reservation)

    remaining_count = count - len(reservations)
    if remaining_count <= 0:
        db.flush()
        return reservations

    max_sequence = _max_direct_sequence(db, prefix, year_month)
    for offset in range(1, remaining_count + 1):
        sequence_no = max_sequence + offset
        reservations.append(
            PlateNumberReservation(
                plate_no=f"{prefix}{year_month}{sequence_no:03d}",
                prefix=prefix,
                year_month=year_month,
                sequence_no=sequence_no,
                status="reserved",
                assigned_user_id=user.id,
                created_by=user.id,
                updated_by=user.id,
            )
        )
    db.add_all(reservations)
    db.flush()
    return reservations


def get_usable_reservation(db: Session, *, user: User, reservation_id: object) -> PlateNumberReservation:
    try:
        lookup_id = reservation_id if isinstance(reservation_id, UUID) else UUID(str(reservation_id))
    except (TypeError, ValueError):
        raise ValueError("Invalid reserved plate number.") from None

    reservation = db.get(PlateNumberReservation, lookup_id)
    if reservation is None or reservation.deleted_at is not None:
        raise ValueError("Reserved plate number not found.")
    if reservation.assigned_user_id != user.id:
        raise ValueError("This plate number belongs to another account.")
    if reservation.status != "reserved":
        raise ValueError("This plate number is no longer available.")
    return reservation


def mark_reservation_used(
    reservation: PlateNumberReservation,
    *,
    order_id: UUID,
    user_id: UUID,
) -> None:
    reservation.status = "used"
    reservation.used_order_id = order_id
    reservation.used_at = datetime.now(timezone.utc)
    reservation.updated_by = user_id


def return_plate_number(db: Session, *, user: User, reservation_id: UUID) -> PlateNumberReservation:
    reservation = get_usable_reservation(db, user=user, reservation_id=reservation_id)
    reservation.status = "available"
    reservation.assigned_user_id = None
    reservation.returned_at = datetime.now(timezone.utc)
    reservation.updated_by = user.id
    db.flush()
    return reservation


def next_derived_plate_number(
    db: Session,
    *,
    source_plate_no: object,
    derivation_type: str,
) -> str:
    source = normalize_plate_number(source_plate_no)
    if not source:
        raise ValueError("Source plate number is required.")
    derivation_type = normalize_derivation_type(derivation_type)
    suffix = DERIVATION_SUFFIX_BY_TYPE[derivation_type]
    _lock_key(db, f"plate-number-derived:{source}:{suffix}")

    pattern = f"{source}{suffix}%"
    candidates = set(_order_plate_candidates(db, pattern))
    reservation_rows = (
        db.query(PlateNumberReservation.plate_no)
        .filter(func.upper(PlateNumberReservation.plate_no).like(pattern.upper()))
        .all()
    )
    candidates.update(normalize_plate_number(row[0]) for row in reservation_rows)

    matcher = re.compile(rf"^{re.escape(source)}{re.escape(suffix)}(\d+)$", re.IGNORECASE)
    max_count = 0
    for candidate in candidates:
        match = matcher.match(candidate)
        if match:
            max_count = max(max_count, int(match.group(1)))
    return f"{source}{suffix}{max_count + 1}"
