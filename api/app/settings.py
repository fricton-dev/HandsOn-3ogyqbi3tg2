"""アプリ設定 (ストレージの切り替え先) の保存と、現在有効なストレージの提供。

設定自体はローカルの PostgreSQL (app_settings テーブル) に保存する。
共有モード (DynamoDB) でもこの EC2 の設定は PostgreSQL に残るので、いつでも戻せる。
"""
import threading

from . import db
from .images_s3 import S3Images
from .storage_dynamodb import DynamoStorage
from .storage_postgres import PostgresStorage

DEFAULTS = {
    "mode": "postgres",          # postgres | dynamodb
    "table": "",
    "region": "ap-northeast-1",
    "endpoint_url": "",          # 通常は空。DynamoDB Local で検証する時だけ使う
    "access_key_id": "",
    "secret_access_key": "",
    "image_bucket": "",          # 共有モードで画像を置く S3 バケット (空なら共有モードでは画像を送れない)
    "s3_endpoint_url": "",       # 通常は空。MinIO など S3 互換環境で検証する時だけ使う
}
_lock = threading.Lock()
_active = None
_active_cfg = None
_images = None


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


def build_images(cfg: dict):
    """画像用 S3 バケットが設定されていればそのクライアント、無ければ None。"""
    if not cfg.get("image_bucket"):
        return None
    return S3Images(bucket=cfg["image_bucket"], region=cfg["region"], access_key_id=cfg.get("access_key_id", ""),
                    secret_access_key=cfg.get("secret_access_key", ""), endpoint_url=cfg.get("s3_endpoint_url", ""))


def _ensure_loaded() -> None:
    global _active, _active_cfg, _images
    if _active is None:
        _active_cfg = load()
        _active = build_backend(_active_cfg)
        _images = build_images(_active_cfg)


def active():
    """現在有効なストレージ。設定が変わるまで同じインスタンスを返す。"""
    with _lock:
        _ensure_loaded()
        return _active


def current() -> dict:
    """現在有効な設定 (コピー)。"""
    with _lock:
        _ensure_loaded()
        return dict(_active_cfg)


def images():
    """画像用 S3 クライアント。バケット未設定なら None。"""
    with _lock:
        _ensure_loaded()
        return _images


def apply(cfg: dict) -> None:
    """設定を保存して、有効なストレージを差し替える。"""
    global _active, _active_cfg, _images
    with _lock:
        save(cfg)
        _active_cfg = dict(cfg)
        _active = build_backend(_active_cfg)
        _images = build_images(_active_cfg)


def public_view(cfg: dict | None = None) -> dict:
    cfg = cfg or load()
    shared = cfg["mode"] == "dynamodb"
    return {"mode": cfg["mode"], "table": cfg["table"] if shared else "",
            "region": cfg["region"] if shared else "",
            "image_bucket": cfg.get("image_bucket", "") if shared else ""}


def masked_view(cfg: dict | None = None) -> dict:
    cfg = cfg or load()
    out = dict(cfg)
    out["secret_access_key"] = "********" if cfg.get("secret_access_key") else ""
    out["has_secret"] = bool(cfg.get("secret_access_key"))
    return out
