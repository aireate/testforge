import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "testforge.db"


class Base(DeclarativeBase):
    pass


def resolve_db_path() -> Path:
    """被测库文件路径，测试时通过 TESTFORGE_DB 注入临时文件实现隔离。"""
    return Path(os.getenv("TESTFORGE_DB", str(DEFAULT_DB_PATH)))


def build_engine(db_path: Path | None = None):
    path = db_path or resolve_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False, "timeout": 15},
        future=True,
    )


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # 导入模型以完成注册
    from sut import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
