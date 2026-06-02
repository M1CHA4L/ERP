from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str
    mac_address: str | None = Field(default=None, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=72)


class UserProfile(BaseModel):
    id: UUID
    username: str
    real_name: str
    roles: list[str]
    permissions: list[str]
    device_mac_address: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
