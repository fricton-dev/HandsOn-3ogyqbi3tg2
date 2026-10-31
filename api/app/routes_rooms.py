"""トークルーム・メッセージ・既読・送信取消・画像アップロード。"""
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import auth, db, services
from .ws import manager

router = APIRouter(prefix="/api")

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}


class RoomCreate(BaseModel):
    type: str = Field(pattern="^(direct|group)$")
    name: str | None = Field(default=None, max_length=50)
    member_ids: list[int] = Field(min_length=1)


class MessageIn(BaseModel):
    type: str = Field(pattern="^(text|sticker)$")
    content: str = Field(min_length=1, max_length=2000)


class ReadIn(BaseModel):
    message_id: int


def _require_member(c, room_id: int, user_id: int) -> None:
    if not services.is_member(c, room_id, user_id):
        raise HTTPException(404, "ルームが見つかりません")


def _insert_message(c, room_id: int, sender_id: int, mtype: str, content: str) -> dict:
    row = c.execute(
        """INSERT INTO messages (room_id, sender_id, type, content)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (room_id, sender_id, mtype, content),
    ).fetchone()
    # 自分の送ったメッセージは自分にとって既読
    c.execute(
        """UPDATE room_members SET last_read_message_id = GREATEST(last_read_message_id, %s)
           WHERE room_id = %s AND user_id = %s""",
        (row["id"], room_id, sender_id),
    )
    return services.get_message(c, row["id"])


def _broadcast_message(c, msg: dict) -> None:
    members = services.room_member_ids(c, msg["room_id"])
    manager.send_threadsafe(members, {"type": "message", "room_id": msg["room_id"], "message": msg})


# ---------- ルーム ----------
@router.get("/rooms")
def list_rooms(me: dict = Depends(auth.current_user)):
    with db.conn() as c:
        return services.list_rooms(c, me["id"])


@router.post("/rooms", status_code=201)
def create_room(body: RoomCreate, me: dict = Depends(auth.current_user)):
    member_ids = sorted({*body.member_ids, me["id"]})
    with db.conn() as c:
        found = c.execute(
            "SELECT COUNT(*) AS n FROM users WHERE id = ANY(%s)", (member_ids,)
        ).fetchone()["n"]
        if found != len(member_ids):
            raise HTTPException(400, "存在しないユーザーが含まれています")

        if body.type == "direct":
            if len(member_ids) != 2:
                raise HTTPException(400, "1:1 トークは相手を 1 人だけ指定してください")
            # 既存の 1:1 ルームがあればそれを返す
            existing = c.execute(
                """SELECT r.id FROM rooms r
                   WHERE r.type = 'direct'
                     AND (SELECT array_agg(user_id ORDER BY user_id) FROM room_members WHERE room_id = r.id) = %s::int[]
                   LIMIT 1""",
                (member_ids,),
            ).fetchone()
            if existing:
                return services.room_summary(c, existing["id"], me["id"])
            name = None
        else:
            name = (body.name or "").strip() or "グループ"

        room = c.execute(
            "INSERT INTO rooms (type, name, created_by) VALUES (%s, %s, %s) RETURNING id",
            (body.type, name, me["id"]),
        ).fetchone()
        for uid in member_ids:
            c.execute("INSERT INTO room_members (room_id, user_id) VALUES (%s, %s)", (room["id"], uid))
        if body.type == "group":
            _insert_message(c, room["id"], me["id"], "system", f"{me['display_name']}がグループを作成しました")
        c.commit()

        # 各メンバーに「自分視点」のルーム情報を送る
        for uid in member_ids:
            manager.send_threadsafe(
                [uid], {"type": "room_created", "room": services.room_summary(c, room["id"], uid)}
            )
        return services.room_summary(c, room["id"], me["id"])


@router.get("/rooms/{room_id}")
def get_room(room_id: int, me: dict = Depends(auth.current_user)):
    with db.conn() as c:
        _require_member(c, room_id, me["id"])
        return services.room_summary(c, room_id, me["id"])


# ---------- メッセージ ----------
@router.get("/rooms/{room_id}/messages")
def list_messages(room_id: int, before: int | None = None, limit: int = 50,
                  me: dict = Depends(auth.current_user)):
    limit = max(1, min(limit, 100))
    with db.conn() as c:
        _require_member(c, room_id, me["id"])
        if before:
            rows = c.execute(
                services.MSG_SELECT + " WHERE m.room_id = %s AND m.id < %s ORDER BY m.id DESC LIMIT %s",
                (room_id, before, limit),
            ).fetchall()
        else:
            rows = c.execute(
                services.MSG_SELECT + " WHERE m.room_id = %s ORDER BY m.id DESC LIMIT %s",
                (room_id, limit),
            ).fetchall()
    rows.reverse()
    return {"messages": [services.serialize_message(r) for r in rows], "has_more": len(rows) == limit}


@router.post("/rooms/{room_id}/messages", status_code=201)
def send_message(room_id: int, body: MessageIn, me: dict = Depends(auth.current_user)):
    with db.conn() as c:
        _require_member(c, room_id, me["id"])
        msg = _insert_message(c, room_id, me["id"], body.type, body.content.strip())
        c.commit()
        _broadcast_message(c, msg)
    return msg


@router.post("/rooms/{room_id}/images", status_code=201)
def send_image(room_id: int, file: UploadFile = File(...), me: dict = Depends(auth.current_user)):
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
    with db.conn() as c:
        _require_member(c, room_id, me["id"])
        msg = _insert_message(c, room_id, me["id"], "image", f"/uploads/{name}")
        c.commit()
        _broadcast_message(c, msg)
    return msg


@router.post("/rooms/{room_id}/read")
def mark_read(room_id: int, body: ReadIn, me: dict = Depends(auth.current_user)):
    with db.conn() as c:
        _require_member(c, room_id, me["id"])
        row = c.execute(
            """UPDATE room_members SET last_read_message_id = GREATEST(last_read_message_id, %s)
               WHERE room_id = %s AND user_id = %s RETURNING last_read_message_id""",
            (body.message_id, room_id, me["id"]),
        ).fetchone()
        c.commit()
        members = services.room_member_ids(c, room_id)
    manager.send_threadsafe(
        members,
        {"type": "read", "room_id": room_id, "user_id": me["id"],
         "last_read_message_id": row["last_read_message_id"]},
    )
    return {"last_read_message_id": row["last_read_message_id"]}


@router.delete("/messages/{message_id}")
def unsend_message(message_id: int, me: dict = Depends(auth.current_user)):
    with db.conn() as c:
        row = c.execute("SELECT room_id, sender_id, deleted_at FROM messages WHERE id = %s", (message_id,)).fetchone()
        if not row or row["sender_id"] != me["id"]:
            raise HTTPException(404, "メッセージが見つかりません")
        if row["deleted_at"] is None:
            c.execute("UPDATE messages SET deleted_at = NOW() WHERE id = %s", (message_id,))
            c.commit()
        msg = services.get_message(c, message_id)
        members = services.room_member_ids(c, row["room_id"])
    manager.send_threadsafe(members, {"type": "message_deleted", "room_id": row["room_id"], "message": msg})
    return msg
