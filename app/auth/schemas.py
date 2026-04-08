import uuid
from pydantic import BaseModel
from app.auth.models import UserRole


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: UserRole
    company: str | None

    class Config:
        from_attributes = True
