import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.auth.models import UserRole


class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: UserRole
    company: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    role: UserRole | None = None
    company: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: UserRole
    company: str | None
    is_active: bool


class RegistrationRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
