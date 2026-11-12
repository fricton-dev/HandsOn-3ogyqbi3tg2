"""ストレージ設定 (ローカル PostgreSQL / 共有 DynamoDB) の参照・接続テスト・切り替え。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import auth, settings

router = APIRouter(prefix="/api/settings")


class SettingsIn(BaseModel):
    mode: str = Field(pattern="^(postgres|dynamodb)$")
    table: str = Field(default="", max_length=255)
    region: str = Field(default="ap-northeast-1", max_length=30)
    endpoint_url: str = Field(default="", max_length=255)
    access_key_id: str = Field(default="", max_length=128)
    secret_access_key: str = Field(default="", max_length=128)
    image_bucket: str = Field(default="", max_length=63)
    s3_endpoint_url: str = Field(default="", max_length=255)


def _merge(body: SettingsIn) -> dict:
    cur = settings.load()
    cfg = {**cur, **body.model_dump()}
    # シークレットが伏せ字のまま送られてきたら既存値を維持
    if body.secret_access_key in ("", "********") and cur.get("secret_access_key"):
        cfg["secret_access_key"] = cur["secret_access_key"] if body.access_key_id == cur.get("access_key_id") else ""
    for k in ("table", "region", "endpoint_url", "access_key_id", "secret_access_key", "image_bucket", "s3_endpoint_url"):
        cfg[k] = (cfg.get(k) or "").strip()
    if cfg["mode"] == "dynamodb" and not cfg["table"]:
        raise HTTPException(400, "テーブル名を入力してください")
    return cfg


def _test(cfg: dict) -> dict:
    """ストレージに接続できるか確かめる。共有モードで画像用バケットがあれば、そちらも書き込みを試す。"""
    try:
        result = settings.build_backend(cfg).ping()
        if cfg["mode"] == "dynamodb" and cfg.get("image_bucket"):
            img = settings.build_images(cfg).ping()
            result = {**result, "detail": f"{result['detail']} {img['detail']}"}
        elif cfg["mode"] == "dynamodb":
            result = {**result, "detail": f"{result['detail']} 画像用 S3 バケットが未設定のため、共有モードでは画像を送れません。"}
        return result
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e))


@router.get("/public")
def public_settings():
    """ログイン前でも見られる情報 (現在のモード)。"""
    return settings.public_view()


@router.get("")
def get_settings(_: dict = Depends(auth.current_user)):
    return settings.masked_view()


@router.post("/test")
def test_settings(body: SettingsIn, _: dict = Depends(auth.current_user)):
    return _test(_merge(body))


@router.put("")
def put_settings(body: SettingsIn, _: dict = Depends(auth.current_user)):
    cfg = _merge(body)
    result = _test(cfg)
    settings.apply(cfg)
    return {"saved": True, "public": settings.public_view(cfg), **result}
