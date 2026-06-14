from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.rbac import User
from app.models.sales import PlateNumberReservation
from app.schemas.sales import PlateNumberDerivedPreview, PlateNumberReservationRead, PlateNumberReserveRequest
from app.services.audit import log_operation
from app.services.plate_numbers import next_derived_plate_number, reserve_plate_numbers, return_plate_number

router = APIRouter()


def _bad_request(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))


@router.get("/my", response_model=list[PlateNumberReservationRead])
def list_my_plate_numbers(
    status_filter: str | None = Query(default="reserved", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> list[PlateNumberReservation]:
    query = (
        db.query(PlateNumberReservation)
        .filter(
            PlateNumberReservation.deleted_at.is_(None),
            PlateNumberReservation.assigned_user_id == current_user.id,
        )
        .order_by(PlateNumberReservation.created_at.desc(), PlateNumberReservation.sequence_no.desc())
    )
    if status_filter:
        query = query.filter(PlateNumberReservation.status == status_filter)
    return query.all()


@router.post("/reserve", response_model=list[PlateNumberReservationRead], status_code=status.HTTP_201_CREATED)
def reserve_my_plate_numbers(
    payload: PlateNumberReserveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:create")),
) -> list[PlateNumberReservation]:
    try:
        reservations = reserve_plate_numbers(
            db,
            user=current_user,
            plate_number_kind=payload.plate_number_kind,
            count=payload.count,
        )
    except ValueError as error:
        raise _bad_request(error) from None
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="reserve_plate_numbers",
        target_type="plate_number_reservation",
        after_data={"count": len(reservations), "plate_numbers": [item.plate_no for item in reservations]},
    )
    db.commit()
    for reservation in reservations:
        db.refresh(reservation)
    return reservations


@router.post("/{reservation_id}/return", response_model=PlateNumberReservationRead)
def return_my_plate_number(
    reservation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:create")),
) -> PlateNumberReservation:
    try:
        reservation = return_plate_number(db, user=current_user, reservation_id=reservation_id)
    except ValueError as error:
        raise _bad_request(error) from None
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="return_plate_number",
        target_type="plate_number_reservation",
        target_id=reservation.id,
        after_data={"plate_no": reservation.plate_no},
    )
    db.commit()
    db.refresh(reservation)
    return reservation


@router.get("/derive-preview", response_model=PlateNumberDerivedPreview)
def preview_derived_plate_number(
    source_plate_no: str = Query(min_length=1),
    derivation_type: str = Query(pattern="^(revision|remake|internal_rework|external_rework)$"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("order:view")),
) -> PlateNumberDerivedPreview:
    try:
        plate_no = next_derived_plate_number(db, source_plate_no=source_plate_no, derivation_type=derivation_type)
    except ValueError as error:
        raise _bad_request(error) from None
    return PlateNumberDerivedPreview(
        source_plate_no=source_plate_no.strip().upper(),
        derivation_type=derivation_type,
        plate_no=plate_no,
    )
