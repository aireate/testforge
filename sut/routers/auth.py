from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from sut.database import get_db
from sut.deps import get_current_user
from sut.errors import AppError
from sut.models import User
from sut.schemas import LoginRequest, TokenOut, UserOut
from sut.security import TOKEN_TTL_MINUTES, create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.username, user.role),
        expires_in=TOKEN_TTL_MINUTES * 60,
        user=UserOut(id=user.id, username=user.username, role=user.role),
    )


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        # 用户名不存在与密码错误返回同一错误，避免账号枚举
        raise AppError(401, "INVALID_CREDENTIALS", "用户名或密码错误")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, username=user.username, role=user.role)


@router.post("/refresh", response_model=TokenOut)
def refresh(user: User = Depends(get_current_user)) -> TokenOut:
    return _token_response(user)
