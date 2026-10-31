"""PostgreSQL への接続まわり。研修用なので最小限の実装にしている。"""
import os
import time

import psycopg

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://app:app_password@localhost:5432/appdb"
)


def get_connection() -> psycopg.Connection:
    """接続を1本返す。呼び出し側で with 文を使って閉じること。"""
    return psycopg.connect(DATABASE_URL)


def wait_for_db(retries: int = 30, interval: float = 1.0) -> None:
    """DB が起動しきるまで待つ。compose の healthcheck と二重の安全策。"""
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            with get_connection() as conn:
                conn.execute("SELECT 1")
            return
        except Exception as e:  # noqa: BLE001
            last_error = e
            time.sleep(interval)
    raise RuntimeError(f"DB に接続できませんでした: {last_error}")
