from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_permission
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.rbac import Role, User
from app.schemas.user import RoleRead, UserCreate, UserRead, UserUpdate

router = APIRouter()


def _serialize_user(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        department=user.department,
        phone=user.phone,
        email=user.email,
        status=user.status,
        device_mac_address=user.device_mac_address,
        device_bound_at=user.device_bound_at,
        last_login_at=user.last_login_at,
        roles=[role.code for role in user.roles],
    )


def _assert_user_list_permission(current_user: User) -> None:
    if "system:permission" not in current_user.permission_codes and "work_order:dispatch" not in current_user.permission_codes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _get_roles_by_code(db: Session, role_codes: list[str]) -> list[Role]:
    if not role_codes:
        return []
    roles = db.query(Role).filter(Role.code.in_(role_codes), Role.status == "active").all()
    found_codes = {role.code for role in roles}
    missing = sorted(set(role_codes) - found_codes)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown or disabled roles: {', '.join(missing)}",
        )
    return roles


@router.get("", response_model=list[UserRead])
def list_users(
    role_code: str | None = None,
    include_disabled: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserRead]:
    _assert_user_list_permission(current_user)
    query = db.query(User).options(selectinload(User.roles))
    if "system:permission" not in current_user.permission_codes or not include_disabled:
        query = query.filter(User.status == "active", User.deleted_at.is_(None))
    if role_code:
        query = query.filter(User.roles.any(code=role_code))
    users = query.order_by(User.created_at.desc()).all()
    return [_serialize_user(user) for user in users]


@router.get("/roles", response_model=list[RoleRead])
def list_roles(
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:permission")),
) -> list[Role]:
    return db.query(Role).filter(Role.status == "active").order_by(Role.code).all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:permission")),
) -> UserRead:
    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.")

    user = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        real_name=payload.real_name,
        phone=payload.phone,
        email=payload.email,
        department=payload.department,
        status=payload.status,
    )
    user.roles = _get_roles_by_code(db, payload.roles)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _serialize_user(user)


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:permission")),
) -> UserRead:
    user = db.query(User).options(selectinload(User.roles)).filter(User.id == user_id).first()
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "password" in updates and updates["password"]:
        user.password_hash = get_password_hash(updates.pop("password"))
    for field in ("real_name", "phone", "email", "department", "status"):
        if field in updates:
            setattr(user, field, updates[field])
    if payload.roles is not None:
        user.roles = _get_roles_by_code(db, payload.roles)

    db.commit()
    db.refresh(user)
    return _serialize_user(user)


@router.post("/{user_id}/clear-device-binding", response_model=UserRead)
def clear_device_binding(
    user_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:permission")),
) -> UserRead:
    user = db.query(User).options(selectinload(User.roles)).filter(User.id == user_id).first()
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.device_mac_address = None
    user.device_bound_at = None
    db.commit()
    db.refresh(user)
    return _serialize_user(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission("system:permission")),
) -> dict[str, bool]:
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="You cannot delete your own account.")

    user = db.query(User).options(selectinload(User.roles)).filter(User.id == user_id).first()
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if any(role.code == "admin" for role in user.roles):
        active_admin_count = (
            db.query(User)
            .join(User.roles)
            .filter(Role.code == "admin", User.status == "active", User.deleted_at.is_(None))
            .count()
        )
        if active_admin_count <= 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one active admin is required.")

    user.status = "disabled"
    db.commit()
    return {"success": True}
