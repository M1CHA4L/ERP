from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.print_job import PrintJob
from app.services.numbering import generate_number


@dataclass(frozen=True)
class FallbackPrintJob:
    print_no: str


def record_print_job(
    db: Session,
    *,
    document_type: str,
    target_type: str,
    target_id: UUID | None = None,
    printed_by: UUID | None = None,
    template_version: str = "v1",
    snapshot: dict | None = None,
    html_snapshot: str | None = None,
    remark: str | None = None,
) -> PrintJob | FallbackPrintJob:
    print_no = generate_number("PRN")
    job = PrintJob(
        print_no=print_no,
        document_type=document_type,
        target_type=target_type,
        target_id=target_id,
        template_version=template_version,
        printed_by=printed_by,
        printed_at=datetime.now(timezone.utc),
        snapshot=jsonable_encoder(snapshot) if snapshot is not None else None,
        html_snapshot=html_snapshot,
        remark=remark,
    )
    try:
        db.add(job)
        db.flush()
        return job
    except SQLAlchemyError:
        db.rollback()
        return FallbackPrintJob(print_no=print_no)
