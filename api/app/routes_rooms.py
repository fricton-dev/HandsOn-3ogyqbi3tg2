"""トークルーム・メッセージ・既読・送信取消・画像アップロード。"""
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import auth, settings
from .storage_base import NotFoundError
from .ws import manager

router = APIRouter(prefix="/api")

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}


class RoomCreate(BaseModel):
    type: str = Field(pattern="^(direct|group)$")
    name: str | None = Field(default=None, max_length=50)
    member_ids: list[str | int] = Field(min_length=1)


class MessageIn(BaseModel):
    type: str = Field(pattern="^(text|sticker)$")
    content: str = Field(min_length=1, max_length=2000)


class ReadIn(BaseModel):
    message_id: str | int


def _require_member(st, room_id, user_id) -> None:
    if not st.is_member(room_id, user_id):
        raise HTTPException(404, "ルームが見つかりません")


def _broadcast_message(st, msg: dict) -> None:
    members = st.room_member_ids(msg["room_id"])
    manager.send_threadsafe(members, {"type": "message", "room_id": msg["room_id"], "message": msg})


# ---------- ルーム ----------
@router.get("/rooms")
def list_rooms(me: dict = Depends(auth.current_user)):
    return settings.active().list_rooms(me["id"])


@router.post("/rooms", status_code=201)
def create_room(body: RoomCreate, me: dict = Depends(auth.current_user)):
    st = settings.active()
    if body.type == "direct" and len({str(m) for m in body.member_ids} - {str(me["id"])}) != 1:
        raise HTTPException(400, "1:1 トークは相手を 1 人だけ指定してください")
    name = (body.name or "").strip() or "グループ" if body.type == "group" else None
    try:
        room_id = st.create_room(body.type, name, body.member_ids, me)
    except NotFoundError as e:
        raise HTTPException(400, str(e))
    for uid in st.room_member_ids(room_id):
        manager.send_threadsafe([uid], {"type": "room_created", "room": st.room_summary(room_id, uid)})
    return st.room_summary(room_id, me["id"])


@router.get("/rooms/{room_id}")
def get_room(room_id: str, me: dict = Depends(auth.current_user)):
    st = settings.active()
    _require_member(st, room_id, me["id"])
    return st.room_summary(room_id, me["id"])


# ---------- メッセージ ----------
@router.get("/rooms/{room_id}/messages")
def list_messages(room_id: str, before: str | None = None, after: str | None = None, limit: int = 50,
                  me: dict = Depends(auth.current_user)):
    st = settings.active()
    _require_member(st, room_id, me["id"])
    msgs, has_more = st.list_messages(room_id, before or None, after or None, max(1, min(limit, 100)))
    return {"messages": msgs, "has_more": has_more}


@router.post("/rooms/{room_id}/messages", status_code=201)
def send_message(room_id: str, body: MessageIn, me: dict = Depends(auth.current_user)):
    st = settings.active()
    _require_member(st, room_id, me["id"])
    msg = st.insert_message(room_id, me, body.type, body.content.strip())
    _broadcast_message(st, msg)
    return msg


@router.post("/rooms/{room_id}/images", status_code=201)
def send_image(room_id: str, file: UploadFile = File(...), me: dict = Depends(auth.current_user)):
    st = settings.active()
    _require_member(st, room_id, me["id"])
    ext = ALLOWED_IMAGE.get(file.content_type or "")
    if not ext:
        raise HTTPException(400, "JPEG / PNG / GIF / WebP の画像のみ送れます")
    data = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "画像は 5MB までです")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(data)
    msg = st.insert_message(room_id, me, "image", f"/uploads/{name}")
    _broadcast_message(st, msg)
    return msg


@router.post("/rooms/{room_id}/read")
def mark_read(room_id: str, body: ReadIn, me: dict = Depends(auth.current_user)):
    st = settings.active()
    _require_member(st, room_id, me["id"])
    last = st.mark_read(room_id, me["id"], body.message_id)
    manager.send_threadsafe(st.room_member_ids(room_id),
                            {"type": "read", "room_id": room_id, "user_id": me["id"], "last_read_message_id": last})
    return {"last_read_message_id": last}


@router.delete("/rooms/{room_id}/messages/{message_id}")
def unsend_message(room_id: str, message_id: str, me: dict = Depends(auth.current_user)):
    st = settings.active()
    msg = st.unsend_message(room_id, message_id, me["id"])
    if not msg:
        raise HTTPException(404, "メッセージが見つかりません")
    manager.send_threadsafe(st.room_member_ids(room_id), {"type": "message_deleted", "room_id": room_id, "message": msg})
    return msg
