"""アプリ設定 (ストレージの切り替え先) の保存と、現在有効なストレージの提供。

設定自体はローカルの PostgreSQL (app_settings テーブル) に保存する。
共有モード (DynamoDB) でもこの EC2 の設定は PostgreSQL に残るので、いつでも戻せる。
"""
import threading

from . import db
from .storage_dynamodb import DynamoStorage
from .storage_postgres import PostgresStorage

DEFAULTS = {
    "mode": "postgres",          # postgres | dynamodb
    "table": "",
    "region": "ap-northeast-1",
    "endpoint_url": "",          # 通常は空。DynamoDB Local で検証する時だけ使う
    "access_key_id": "",
    "secret_access_key": "",
}
_lock = threading.Lock()
_active = None
_active_cfg = None


def ensure_table() -> None:
    with db.conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")


def load() -> dict:
    cfg = dict(DEFAULTS)
    with db.conn() as c:
        for row in c.execute("SELECT key, value FROM app_settings").fetchall():
            if row["key"] in cfg:
                cfg[row["key"]] = row["value"]
    return cfg


def save(cfg: dict) -> None:
    with db.conn() as c:
        for k in DEFAULTS:
            c.execute(
                "INSERT INTO app_settings (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (k, str(cfg.get(k, DEFAULTS[k]))),
            )


def build_backend(cfg: dict):
    if cfg.get("mode") == "dynamodb":
        return DynamoStorage(table=cfg["table"], region=cfg["region"], access_key_id=cfg.get("access_key_id", ""),
                             secret_access_key=cfg.get("secret_access_key", ""), endpoint_url=cfg.get("endpoint_url", ""))
    return PostgresStorage()


def active():
    """現在有効なストレージ。設定が変わるまで同じインスタンスを返す。"""
    global _active, _active_cfg
    with _lock:
        if _active is None:
            _active_cfg = load()
            _active = build_backend(_active_cfg)
        return _active


def apply(cfg: dict) -> None:
    """設定を保存して、有効なストレージを差し替える。"""
    global _active, _active_cfg
    with _lock:
        save(cfg)
        _active_cfg = dict(cfg)
        _active = build_backend(_active_cfg)


def public_view(cfg: dict | None = None) -> dict:
    cfg = cfg or load()
    return {"mode": cfg["mode"], "table": cfg["table"] if cfg["mode"] == "dynamodb" else "",
            "region": cfg["region"] if cfg["mode"] == "dynamodb" else ""}


def masked_view(cfg: dict | None = None) -> dict:
    cfg = cfg or load()
    out = dict(cfg)
    out["secret_access_key"] = "********" if cfg.get("secret_access_key") else ""
    out["has_secret"] = bool(cfg.get("secret_access_key"))
    return out
