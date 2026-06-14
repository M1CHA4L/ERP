from uuid import UUID

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    real_name: str
    department: str | None
    phone: str | None = None
    email: str | None = None
    status: str
    device_mac_address: str | None = None
    device_bound_at: datetime | None = None
    last_login_at: datetime | None = None
    roles: list[str] = []
    role_permissions: list[str] = []
    extra_permissions: list[str] = []
    disabled_permissions: list[str] = []
    permissions: list[str] = []


class UserOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    real_name: str
    department: str | None
    status: str
    roles: list[str] = []


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    status: str
    permissions: list[str] = []


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    type: str
    sort_no: int


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    real_name: str = Field(min_length=1, max_length=64)
    phone: str | None = None
    email: str | None = None
    department: str | None = None
    status: str = "active"
    roles: list[str] = []
    extra_permissions: list[str] = []
    disabled_permissions: list[str] = []


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=72)
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    phone: str | None = None
    email: str | None = None
    department: str | None = None
    status: str | None = None
    roles: list[str] | None = None
    extra_permissions: list[str] | None = None
    disabled_permissions: list[str] | None = None
