from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.operation_log import OperationLog


def log_operation(
    db: Session,
    *,
    user_id: UUID,
    module: str,
    action: str,
    target_type: str,
    target_id: UUID | None = None,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> None:
    db.add(
        OperationLog(
            user_id=user_id,
            module=module,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_data=before_data,
            after_data=after_data,
            created_at=datetime.now(timezone.utc),
        )
    )
