from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import JWTError, decode_token

_bearer = HTTPBearer(auto_error=False)


def _user_from_token(token: str | None, db: Session, token_type: str) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = decode_token(token)
        if payload.get("type") != token_type:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token") from None

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else None
    return _user_from_token(token, db, "access")


def get_refresh_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else None
    return _user_from_token(token, db, "refresh")


def require_roles(*roles):
    """Accept require_roles('admin') or require_roles(['admin', 'accountant'])."""
    if len(roles) == 1 and isinstance(roles[0], (list, tuple, set)):
        allowed = set(roles[0])
    else:
        allowed = set(roles)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker
