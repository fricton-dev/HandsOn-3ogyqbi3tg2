"""送信画像の保存先。

- ローカルモード (PostgreSQL): これまでどおり EC2 のボリューム (UPLOAD_DIR) に保存する。
- 共有モード (DynamoDB) で IMAGE_BUCKET が設定されている場合: S3 バケットに保存する。
  メッセージには従来と同じ "/uploads/<ファイル名>" を入れ、GET /uploads/<ファイル名> で
  手元に無ければ S3 の署名付き URL へリダイレクトする。
  これで別の EC2 から送られた画像も、どの EC2 の画面からでも表示できる。

バケットは非公開のまま (パブリックアクセスはブロック)。読み書きは EC2 の IAM ロールで行う。
"""
import os
import re

import boto3
from botocore.config import Config

from . import settings

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
IMAGE_BUCKET = os.environ.get("IMAGE_BUCKET", "").strip()
IMAGE_BUCKET_REGION = os.environ.get("IMAGE_BUCKET_REGION", "ap-northeast-1").strip() or "ap-northeast-1"
IMAGE_PREFIX = "chat-images/"
URL_EXPIRES = 3600  # 署名付き URL の有効期限 (秒)

NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|gif|webp)$")
CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}


def _s3():
    """S3 クライアント。設定画面でアクセスキーを入れている場合はそれを、無ければ IAM ロールを使う。"""
    kwargs = {"region_name": IMAGE_BUCKET_REGION}
    try:
        cfg = settings.load()
        if cfg.get("access_key_id") and cfg.get("secret_access_key"):
            kwargs.update(aws_access_key_id=cfg["access_key_id"], aws_secret_access_key=cfg["secret_access_key"])
    except Exception:  # noqa: BLE001
        pass
    return boto3.session.Session(**kwargs).client(
        "s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"},
                            connect_timeout=3, read_timeout=10, retries={"max_attempts": 2}))


def use_s3() -> bool:
    """共有モードで、かつバケットが設定されているときだけ S3 に保存する。"""
    if not IMAGE_BUCKET:
        return False
    try:
        return getattr(settings.active(), "name", "") == "dynamodb"
    except Exception:  # noqa: BLE001
        return False


def save(name: str, data: bytes) -> str:
    """画像を保存し、メッセージに入れるパスを返す。"""
    if use_s3():
        ext = name.rsplit(".", 1)[-1]
        _s3().put_object(Bucket=IMAGE_BUCKET, Key=IMAGE_PREFIX + name, Body=data,
                         ContentType=CONTENT_TYPES.get(ext, "application/octet-stream"))
    else:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
            f.write(data)
    return f"/uploads/{name}"


def local_path(name: str) -> str | None:
    if not NAME_RE.match(name):
        return None
    path = os.path.join(UPLOAD_DIR, name)
    return path if os.path.isfile(path) else None


def presigned_url(name: str) -> str | None:
    if not IMAGE_BUCKET or not NAME_RE.match(name):
        return None
    return _s3().generate_presigned_url(
        "get_object", Params={"Bucket": IMAGE_BUCKET, "Key": IMAGE_PREFIX + name}, ExpiresIn=URL_EXPIRES)


def info() -> dict:
    return {"bucket": IMAGE_BUCKET or None, "region": IMAGE_BUCKET_REGION if IMAGE_BUCKET else None,
            "backend": "s3" if use_s3() else "local"}
