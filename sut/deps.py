from fastapi import Depends, Header
from sqlalchemy.orm import Session

import jwt
from sut import faults
from sut.database import get_db
from sut.errors import AppError
from sut.models import User
from sut.security import decode_access_token


def _unauthorized(message: str, code: str = "UNAUTHORIZED") -> AppError:
    return AppError(401, code, message)


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("缺少 Bearer Token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(
            token, verify_exp=not faults.enabled("token_expiry_ignored")
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token 已过期", "TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Token 无效", "TOKEN_INVALID") from exc

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise _unauthorized("用户不存在", "USER_NOT_FOUND")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin" and not faults.enabled("admin_check_removed"):
        raise AppError(403, "FORBIDDEN", "需要管理员权限")
    return user
