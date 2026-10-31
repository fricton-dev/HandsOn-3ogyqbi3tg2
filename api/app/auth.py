"""認証: パスワードハッシュ(PBKDF2) と、トークンからユーザーを特定する依存関係。"""
import hashlib
import hmac
import secrets

from fastapi import Header, HTTPException

from . import settings

_ITER = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITER).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITER).hex()
    return hmac.compare_digest(calc, digest)


def bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def user_from_token(token: str | None) -> dict | None:
    try:
        return settings.active().user_from_token(token)
    except Exception:  # noqa: BLE001  (共有ストレージに繋がらない等)
        return None


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI の依存関係。Authorization: Bearer <token> からユーザーを特定する。"""
    token = bearer_token(authorization)
    user = user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="ログインが必要です")
    user["_token"] = token
    return user
