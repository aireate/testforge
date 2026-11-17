import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

JWT_ALGORITHM = "HS256"
JWT_SECRET = os.getenv(
    "TESTFORGE_JWT_SECRET", "testforge-local-dev-secret-please-override-in-prod"
)
TOKEN_TTL_MINUTES = int(os.getenv("TESTFORGE_TOKEN_TTL", "120"))
_PBKDF2_ROUNDS = 120_000


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS
    )
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, encoded = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(rounds)
        )
        return hmac.compare_digest(digest, base64.b64decode(encoded))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, username: str, role: str, ttl_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes or TOKEN_TTL_MINUTES)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, verify_exp: bool = True) -> dict:
    """解析 token；签名错误或过期时抛出 jwt.PyJWTError。"""
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        options={} if verify_exp else {"verify_exp": False},
    )
