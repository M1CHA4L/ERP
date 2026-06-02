import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.file import FileAsset
from app.models.production import InspectionRecord, WorkOrder, WorkOrderStep
from app.models.rbac import User
from app.models.sales import SalesOrder
from app.schemas.file import FileAssetRead
from app.services.audit import log_operation

router = APIRouter()

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".ai",
    ".cdr",
    ".csv",
    ".doc",
    ".docx",
    ".dwg",
    ".dxf",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".psd",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}
OWNER_MODELS = {
    "sales_order": SalesOrder,
    "work_order": WorkOrder,
    "work_order_step": WorkOrderStep,
    "inspection_record": InspectionRecord,
}
VIEW_PERMISSIONS = {
    "sales_order": ("order:view",),
    "work_order": ("work_order:view",),
    "work_order_step": ("work_order:view",),
    "inspection_record": ("inspection:view",),
}
UPLOAD_PERMISSIONS = {
    "sales_order": ("order:create", "order:update"),
    "work_order": ("work_order:dispatch", "step:report"),
    "work_order_step": ("work_order:dispatch", "step:report"),
    "inspection_record": ("inspection:submit",),
}
DELETE_PERMISSIONS = {
    "sales_order": ("order:update", "system:permission"),
    "work_order": ("work_order:dispatch", "system:permission"),
    "work_order_step": ("work_order:dispatch", "step:report", "system:permission"),
    "inspection_record": ("inspection:submit", "system:permission"),
}


def require_any_permission(user: User, permissions: tuple[str, ...]) -> None:
    if not any(permission in user.permission_codes for permission in permissions):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def validate_owner(db: Session, owner_type: str, owner_id: uuid.UUID):
    model = OWNER_MODELS.get(owner_type)
    if model is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported owner type.")
    owner = db.get(model, owner_id)
    if owner is None or getattr(owner, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found.")
    return owner


def storage_root() -> Path:
    root = Path(settings.file_storage_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_suffix(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported file type.")
    return suffix


def clean_file_name(file_name: str) -> str:
    name = Path(file_name).name.strip() or "upload"
    return re.sub(r"[^\w.\-\u4e00-\u9fff ]+", "_", name)[:255]


@router.get("", response_model=list[FileAssetRead])
def list_files(
    owner_type: str,
    owner_id: uuid.UUID,
    file_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FileAsset]:
    validate_owner(db, owner_type, owner_id)
    require_any_permission(current_user, VIEW_PERMISSIONS.get(owner_type, ()))
    query = db.query(FileAsset).filter(
        FileAsset.owner_type == owner_type,
        FileAsset.owner_id == owner_id,
        FileAsset.deleted_at.is_(None),
    )
    if file_type:
        query = query.filter(FileAsset.file_type == file_type)
    return query.order_by(FileAsset.created_at.desc()).all()


@router.post("/upload", response_model=FileAssetRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    owner_type: str = Form(...),
    owner_id: uuid.UUID = Form(...),
    file_type: str = Form(default="attachment"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileAsset:
    validate_owner(db, owner_type, owner_id)
    require_any_permission(current_user, UPLOAD_PERMISSIONS.get(owner_type, ()))
    suffix = safe_suffix(file.filename or "")
    original_name = clean_file_name(file.filename or f"upload{suffix}")
    file_id = uuid.uuid4()
    relative_path = Path(owner_type) / str(owner_id) / f"{file_id}{suffix}"
    absolute_path = storage_root() / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    try:
        with absolute_path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large.")
                target.write(chunk)
    except Exception:
        if absolute_path.exists():
            absolute_path.unlink()
        raise

    asset = FileAsset(
        id=file_id,
        owner_type=owner_type,
        owner_id=owner_id,
        file_type=file_type,
        file_name=original_name,
        storage_path=relative_path.as_posix(),
        mime_type=file.content_type,
        size_bytes=size,
        uploaded_by=current_user.id,
    )
    db.add(asset)
    log_operation(
        db,
        user_id=current_user.id,
        module="file",
        action="upload",
        target_type=owner_type,
        target_id=owner_id,
        after_data={"file_name": original_name, "file_type": file_type, "size_bytes": size},
    )
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{file_id}/download")
def download_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    asset = db.get(FileAsset, file_id)
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    validate_owner(db, asset.owner_type, asset.owner_id)
    require_any_permission(current_user, VIEW_PERMISSIONS.get(asset.owner_type, ()))
    absolute_path = storage_root() / asset.storage_path
    if not absolute_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found.")
    return FileResponse(absolute_path, media_type=asset.mime_type, filename=asset.file_name)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    asset = db.get(FileAsset, file_id)
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    validate_owner(db, asset.owner_type, asset.owner_id)
    require_any_permission(current_user, DELETE_PERMISSIONS.get(asset.owner_type, ()))
    asset.deleted_at = datetime.now(timezone.utc)
    log_operation(
        db,
        user_id=current_user.id,
        module="file",
        action="delete",
        target_type=asset.owner_type,
        target_id=asset.owner_id,
        before_data={"file_name": asset.file_name, "file_type": asset.file_type},
    )
    db.commit()
