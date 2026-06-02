from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.rbac import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse, UserProfile

router = APIRouter()


def _is_admin_user(user: User) -> bool:
    return any(role.code == "admin" for role in user.roles) or "system:permission" in user.permission_codes


def _normalize_mac_address(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_user_profile(user: User, permissions: list[str]) -> UserProfile:
    return UserProfile(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        roles=[role.code for role in user.roles],
        permissions=permissions,
        device_mac_address=user.device_mac_address,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or user.status != "active" or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    permissions = sorted(user.permission_codes)
    mac_address = _normalize_mac_address(payload.mac_address)
    if not _is_admin_user(user):
        if mac_address is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Device identifier is required.")
        if user.device_mac_address and user.device_mac_address != mac_address:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is bound to another device. Contact an administrator.")
        if not user.device_mac_address:
            user.device_mac_address = mac_address
            user.device_bound_at = datetime.now(timezone.utc)

    token = create_access_token(str(user.id), {"permissions": permissions})
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return TokenResponse(
        access_token=token,
        user=_build_user_profile(user, permissions),
    )


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Current password is incorrect.")
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must be different.")
    current_user.password_hash = get_password_hash(payload.new_password)
    db.commit()
    return {"success": True}
