import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.service import decode_token
from app.database import get_db

_bearer = HTTPBearer()
_bearer_optional = HTTPBearer(auto_error=False)


def _user_from_token(token: str, db: Session) -> User:
    try:
        user_id = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    return _user_from_token(credentials.credentials, db)


def get_current_user_with_query_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
    access_token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Accept token via Bearer header OR ?access_token= query parameter."""
    token = credentials.credentials if credentials else access_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _user_from_token(token, db)


def require_role(*roles: UserRole):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return dependency
