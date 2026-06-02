from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.operation_log import OperationLog
from app.schemas.common import PageResponse
from app.schemas.operation_log import OperationLogRead

router = APIRouter()


@router.get("", response_model=PageResponse[OperationLogRead])
def list_operation_logs(
    module: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("log:view")),
) -> PageResponse[OperationLogRead]:
    query = db.query(OperationLog)
    if module:
        query = query.filter(OperationLog.module == module)
    if action:
        query = query.filter(OperationLog.action == action)
    if target_type:
        query = query.filter(OperationLog.target_type == target_type)
    if target_id:
        query = query.filter(OperationLog.target_id == target_id)
    total = query.count()
    items = query.order_by(OperationLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)
