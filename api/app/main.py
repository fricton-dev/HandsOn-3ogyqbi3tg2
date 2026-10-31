"""研修用 API サーバー (FastAPI)

エンドポイント:
  GET  /api/health    生存確認 (DB には触らない)
  GET  /api/info      API と DB のバージョン情報
  GET  /api/messages  メッセージ一覧 (DB から取得)
  POST /api/messages  メッセージ追加 (DB へ保存)
"""
import os
import socket
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.wait_for_db()
    yield


app = FastAPI(title="Training API", version="1.0.0", lifespan=lifespan)

# ---- CORS ----
# S3 でホスティングした画面(別オリジン)から API を呼ぶために必要。
# CORS_ORIGINS="*" ならすべて許可、カンマ区切りで個別指定も可。
_origins_env = os.environ.get("CORS_ORIGINS", "*")
_origins = ["*"] if _origins_env.strip() == "*" else [
    o.strip() for o in _origins_env.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- モデル ----
class Message(BaseModel):
    id: int
    author: str
    body: str
    created_at: datetime


class MessageCreate(BaseModel):
    author: str = Field(min_length=1, max_length=50)
    body: str = Field(min_length=1, max_length=200)


# ---- エンドポイント ----
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/info")
def info():
    try:
        with db.get_connection() as conn:
            row = conn.execute("SELECT version()").fetchone()
            db_version = row[0] if row else "unknown"
            db_ok = True
    except Exception as e:  # noqa: BLE001
        db_version = f"接続失敗: {e}"
        db_ok = False
    return {
        "api": "FastAPI",
        "api_hostname": socket.gethostname(),
        "db_ok": db_ok,
        "db_version": db_version,
    }


@app.get("/api/messages", response_model=list[Message])
def list_messages():
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT id, author, body, created_at FROM messages ORDER BY id"
        ).fetchall()
    return [
        Message(id=r[0], author=r[1], body=r[2], created_at=r[3]) for r in rows
    ]


@app.post("/api/messages", response_model=Message, status_code=201)
def create_message(payload: MessageCreate):
    with db.get_connection() as conn:
        row = conn.execute(
            "INSERT INTO messages (author, body) VALUES (%s, %s) "
            "RETURNING id, author, body, created_at",
            (payload.author, payload.body),
        ).fetchone()
        conn.commit()
    if row is None:
        raise HTTPException(status_code=500, detail="insert failed")
    return Message(id=row[0], author=row[1], body=row[2], created_at=row[3])
