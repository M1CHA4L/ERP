from datetime import date, datetime, time, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.print_job import PrintJob
from app.schemas.common import PageResponse
from app.schemas.print_job import PrintJobRead

router = APIRouter()


def _day_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _day_end(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


@router.get("", response_model=PageResponse[PrintJobRead])
def list_print_jobs(
    document_type: str | None = None,
    target_type: str | None = None,
    target_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("report:view")),
) -> PageResponse[PrintJobRead]:
    query = db.query(PrintJob).filter(PrintJob.deleted_at.is_(None))
    if document_type:
        query = query.filter(PrintJob.document_type == document_type)
    if target_type:
        query = query.filter(PrintJob.target_type == target_type)
    if target_id:
        query = query.filter(PrintJob.target_id == target_id)
    if date_from:
        query = query.filter(PrintJob.printed_at >= _day_start(date_from))
    if date_to:
        query = query.filter(PrintJob.printed_at <= _day_end(date_to))

    total = query.count()
    items = query.order_by(PrintJob.printed_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)
