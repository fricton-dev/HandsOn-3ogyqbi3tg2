"""ログイン・新規登録・プロフィール・ユーザー検索。"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import auth, services, settings
from .storage_base import ConflictError

router = APIRouter(prefix="/api")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


class SignupIn(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    display_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=4, max_length=100)


class LoginIn(BaseModel):
    username: str
    password: str


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    status_message: str | None = Field(default=None, max_length=100)


def _storage_error(e: Exception) -> HTTPException:
    return HTTPException(503, f"ストレージに接続できません: {str(e)[:200]}")


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn):
    if not USERNAME_RE.match(body.username):
        raise HTTPException(400, "ユーザー名は英数字とアンダースコア 3〜30 文字です")
    st = settings.active()
    try:
        user = st.create_user(body.username, body.display_name.strip(), auth.hash_password(body.password),
                              services.pick_color(body.username))
        token = st.create_session(user["id"])
    except ConflictError as e:
        raise HTTPException(409, str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise _storage_error(e)
    return {"token": token, "user": user}


@router.post("/auth/login")
def login(body: LoginIn):
    st = settings.active()
    try:
        row = st.get_user_with_hash(body.username.strip())
        if not row or not auth.verify_password(body.password, row["password_hash"]):
            raise HTTPException(401, "ユーザー名またはパスワードが違います")
        token = st.create_session(row["id"])
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise _storage_error(e)
    row.pop("password_hash", None)
    return {"token": token, "user": row}


@router.post("/auth/logout", status_code=204)
def logout(me: dict = Depends(auth.current_user)):
    try:
        settings.active().delete_session(me["_token"])
    except Exception:  # noqa: BLE001
        pass


@router.get("/me")
def get_me(me: dict = Depends(auth.current_user)):
    return {k: v for k, v in me.items() if not k.startswith("_")}


@router.patch("/me")
def update_me(body: ProfileIn, me: dict = Depends(auth.current_user)):
    return settings.active().update_user(me["id"], body.display_name, body.status_message)


@router.get("/users")
def list_users(q: str = "", me: dict = Depends(auth.current_user)):
    return settings.active().search_users(q, me["id"])
