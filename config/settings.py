import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    """测试配置。全部可通过环境变量覆盖，便于本地 / CI / 容器复用同一套用例。"""

    base_url: str = "http://127.0.0.1:8000"
    api_prefix: str = "/api/v1"
    timeout: float = 10.0
    retries: int = 2
    admin_username: str = "admin"
    admin_password: str = "admin123"
    user_username: str = "user"
    user_password: str = "user123"
    pay_secret: str = "testforge-pay-secret"
    db_path: Path | None = None

    @property
    def api_base(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.api_prefix}"

    @classmethod
    def from_env(cls) -> "Settings":
        db_path = os.getenv("TESTFORGE_DB")
        return cls(
            base_url=os.getenv("TESTFORGE_BASE_URL", cls.base_url),
            api_prefix=os.getenv("TESTFORGE_API_PREFIX", cls.api_prefix),
            timeout=float(os.getenv("TESTFORGE_TIMEOUT", cls.timeout)),
            retries=int(os.getenv("TESTFORGE_RETRIES", cls.retries)),
            admin_username=os.getenv("TESTFORGE_ADMIN_USER", cls.admin_username),
            admin_password=os.getenv("TESTFORGE_ADMIN_PASSWORD", cls.admin_password),
            user_username=os.getenv("TESTFORGE_USER_USER", cls.user_username),
            user_password=os.getenv("TESTFORGE_USER_PASSWORD", cls.user_password),
            pay_secret=os.getenv("TESTFORGE_PAY_SECRET", cls.pay_secret),
            db_path=Path(db_path) if db_path else None,
        )


settings = Settings.from_env()
