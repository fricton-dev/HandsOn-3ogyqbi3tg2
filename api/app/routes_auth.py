"""ログイン・新規登録・プロフィール・ユーザー検索。"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import auth, db, services

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


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn):
    if not USERNAME_RE.match(body.username):
        raise HTTPException(400, "ユーザー名は英数字とアンダースコア 3〜30 文字です")
    with db.conn() as c:
        if c.execute("SELECT 1 FROM users WHERE username = %s", (body.username,)).fetchone():
            raise HTTPException(409, "そのユーザー名は既に使われています")
        row = c.execute(
            """INSERT INTO users (username, display_name, password_hash, avatar_color)
               VALUES (%s, %s, %s, %s)
               RETURNING id, username, display_name, avatar_color, status_message""",
            (body.username, body.display_name, auth.hash_password(body.password),
             services.pick_color(body.username)),
        ).fetchone()
        token = auth.create_session(c, row["id"])
    return {"token": token, "user": services.serialize_user(row)}


@router.post("/auth/login")
def login(body: LoginIn):
    with db.conn() as c:
        row = c.execute("SELECT * FROM users WHERE username = %s", (body.username,)).fetchone()
        if not row or not auth.verify_password(body.password, row["password_hash"]):
            raise HTTPException(401, "ユーザー名またはパスワードが違います")
        token = auth.create_session(c, row["id"])
    return {"token": token, "user": services.serialize_user(row)}


@router.post("/auth/logout", status_code=204)
def logout(me: dict = Depends(auth.current_user)):
    with db.conn() as c:
        auth.delete_session(c, me["_token"])


@router.get("/me")
def get_me(me: dict = Depends(auth.current_user)):
    return services.serialize_user(me)


@router.patch("/me")
def update_me(body: ProfileIn, me: dict = Depends(auth.current_user)):
    with db.conn() as c:
        row = c.execute(
            """UPDATE users SET display_name = COALESCE(%s, display_name),
                                status_message = COALESCE(%s, status_message)
               WHERE id = %s RETURNING id, username, display_name, avatar_color, status_message""",
            (body.display_name, body.status_message, me["id"]),
        ).fetchone()
    return services.serialize_user(row)


@router.get("/users")
def list_users(q: str = "", me: dict = Depends(auth.current_user)):
    with db.conn() as c:
        rows = c.execute(
            """SELECT id, username, display_name, avatar_color, status_message FROM users
               WHERE id <> %s AND (display_name ILIKE %s OR username ILIKE %s)
               ORDER BY display_name LIMIT 100""",
            (me["id"], f"%{q}%", f"%{q}%"),
        ).fetchall()
    return [services.serialize_user(r) for r in rows]
