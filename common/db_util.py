import sqlite3
import time
from pathlib import Path
from typing import Any, Sequence


class DbUtil:
    """以只读方式直连被测库，用于「接口断言 + 落库断言」双层校验。"""

    def __init__(self, db_path: str | Path, retries: int = 5) -> None:
        self.db_path = Path(db_path)
        self.retries = retries

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            f"file:{self.db_path.as_posix()}?mode=ro", uri=True, timeout=10
        )
        conn.row_factory = sqlite3.Row
        return conn

    def query_all(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        for attempt in range(self.retries):
            try:
                with self._connect() as conn:
                    return conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc) or attempt == self.retries - 1:
                    raise
                time.sleep(0.1 * (attempt + 1))
        return []

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        rows = self.query_all(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Sequence[Any] = (), default: Any = None) -> Any:
        row = self.query_one(sql, params)
        if row is None:
            return default
        return row[0]

    def count(self, table: str, where: str = "", params: Sequence[Any] = ()) -> int:
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += f" WHERE {where}"
        return int(self.scalar(sql, params, default=0))

    def foreign_key_violations(self) -> list[sqlite3.Row]:
        return self.query_all("PRAGMA foreign_key_check")
