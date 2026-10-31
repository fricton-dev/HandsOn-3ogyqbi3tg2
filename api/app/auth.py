"""認証: パスワードハッシュ(PBKDF2) とセッショントークン。"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException

from . import db

SESSION_DAYS = 30
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


def create_session(c, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    c.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
        (token, user_id, expires),
    )
    return token


def delete_session(c, token: str) -> None:
    c.execute("DELETE FROM sessions WHERE token = %s", (token,))


def user_from_token(token: str | None) -> dict | None:
    if not token:
        return None
    with db.conn() as c:
        row = c.execute(
            """SELECT u.id, u.username, u.display_name, u.avatar_color, u.status_message
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token = %s AND s.expires_at > NOW()""",
            (token,),
        ).fetchone()
    return dict(row) if row else None


def bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI の依存関係。Authorization: Bearer <token> からユーザーを特定する。"""
    user = user_from_token(bearer_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="ログインが必要です")
    user["_token"] = bearer_token(authorization)
    return user
