"""PostgreSQL 接続プール。"""
import os
import time
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://app:app_password@localhost:5432/appdb"
)

pool = ConnectionPool(
    DATABASE_URL, min_size=1, max_size=10, open=False, kwargs={"row_factory": dict_row}
)


def open_pool(retries: int = 30, interval: float = 1.0) -> None:
    """DB が起動しきるまで待ってプールを開く。"""
    last: Exception | None = None
    for _ in range(retries):
        try:
            pool.open(wait=True, timeout=5)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(interval)
    raise RuntimeError(f"DB に接続できませんでした: {last}")


def close_pool() -> None:
    pool.close()


@contextmanager
def conn():
    """with db.conn() as c: ... で接続を借りる。ブロックを抜けると自動 commit。"""
    with pool.connection() as c:
        yield c
