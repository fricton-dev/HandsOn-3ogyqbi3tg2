"""共有モードで送られた画像の保存先 (S3)。

共有モードではメッセージ本体は DynamoDB に入るが、画像ファイルはどこかに置く必要がある。
各 EC2 のディスクに置くと他の EC2 からは見えないので、全員共通の S3 バケットに保存する。
ブラウザには自分の EC2 の API (/api/images/<キー>) 経由で返すため、バケットを公開する必要はない。
"""
import re
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

PREFIX = "chat-images/"
_KEY_RE = re.compile(r"^[A-Za-z0-9_\-./]+$")


def valid_key(key: str) -> bool:
    return bool(key) and bool(_KEY_RE.match(key)) and ".." not in key and not key.startswith("/")


class S3Images:
    def __init__(self, bucket: str, region: str, access_key_id: str = "", secret_access_key: str = "",
                 endpoint_url: str = ""):
        kwargs = {"region_name": region or "ap-northeast-1"}
        if access_key_id and secret_access_key:
            kwargs.update(aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key)
        session = boto3.session.Session(**kwargs)
        cfg = Config(connect_timeout=3, read_timeout=15, retries={"max_attempts": 2},
                     s3={"addressing_style": "path"} if endpoint_url else {})
        self.client = session.client("s3", endpoint_url=endpoint_url or None, config=cfg)
        self.bucket = bucket
        self.region = kwargs["region_name"]

    def _wrap(self, e: Exception) -> RuntimeError:
        if isinstance(e, ClientError):
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchBucket", "404"):
                return RuntimeError(f"S3 バケット '{self.bucket}' が見つかりません")
            if code in ("AccessDenied", "403", "InvalidAccessKeyId", "SignatureDoesNotMatch", "AllAccessDisabled"):
                return RuntimeError(f"S3 バケット '{self.bucket}' への権限または認証情報の問題です ({code})。"
                                    "EC2 の IAM ロールに s3:PutObject / GetObject / DeleteObject があるか確認してください")
            if code in ("PermanentRedirect", "IllegalLocationConstraintException", "AuthorizationHeaderMalformed"):
                return RuntimeError(f"S3 バケット '{self.bucket}' のリージョンが設定と違います ({code})")
            return RuntimeError(f"S3 エラー: {code or e}")
        msg = str(e)
        if "Unable to locate credentials" in msg:
            return RuntimeError("AWS の認証情報がありません。EC2 に IAM ロールを付けるか、アクセスキーを入力してください")
        return RuntimeError(f"S3 に接続できません: {msg[:200]}")

    def ping(self) -> dict:
        """書き込み → 削除を 1 回行って、バケットとその権限を確かめる。"""
        key = f"{PREFIX}_probe/{uuid.uuid4().hex}"
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=b"probe", ContentType="text/plain")
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as e:  # noqa: BLE001
            raise self._wrap(e) from e
        return {"ok": True, "detail": f"画像用 S3 バケット '{self.bucket}' に書き込めました。"}

    def put(self, room_id: str, ext: str, data: bytes, content_type: str) -> str:
        """画像を保存し、メッセージに入れるキー (バケット内のパス) を返す。"""
        key = f"{PREFIX}{room_id}/{uuid.uuid4().hex}{ext}"
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type,
                                   CacheControl="public, max-age=31536000, immutable")
        except Exception as e:  # noqa: BLE001
            raise self._wrap(e) from e
        return key

    def get(self, key: str):
        """(本文のストリーム, Content-Type, サイズ) を返す。無ければ None。"""
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code", "") in ("NoSuchKey", "404"):
                return None
            raise self._wrap(e) from e
        except Exception as e:  # noqa: BLE001
            raise self._wrap(e) from e
        return obj["Body"], obj.get("ContentType") or "application/octet-stream", obj.get("ContentLength")
