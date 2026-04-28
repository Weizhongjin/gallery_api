import uuid
from pydantic import BaseModel, ConfigDict, constr
from app.auth.models import UserRole


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: str
    password: constr(min_length=6)
    name: constr(min_length=1, max_length=120)


class RegisterResponse(BaseModel):
    ok: bool = True
    message: str = "注册申请已提交，等待管理员审核"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: UserRole
    company: str | None
