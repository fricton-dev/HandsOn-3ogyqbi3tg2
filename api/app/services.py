"""ルーム・メッセージ共通のクエリと JSON 変換。"""
from datetime import datetime

AVATAR_COLORS = ["#06c755", "#5b8def", "#ff7a59", "#a66bff", "#f5a623", "#e94e77", "#2bb3c0", "#8d6e63"]


def pick_color(seed: str) -> str:
    return AVATAR_COLORS[sum(map(ord, seed)) % len(AVATAR_COLORS)]


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def serialize_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "avatar_color": row["avatar_color"],
        "status_message": row.get("status_message", ""),
    }


MSG_SELECT = """
SELECT m.id, m.room_id, m.sender_id, u.display_name AS sender_name, u.avatar_color AS sender_color,
       m.type, m.content, m.created_at, m.deleted_at
FROM messages m JOIN users u ON u.id = m.sender_id
"""


def serialize_message(row) -> dict:
    deleted = row["deleted_at"] is not None
    return {
        "id": row["id"],
        "room_id": row["room_id"],
        "sender": {
            "id": row["sender_id"],
            "display_name": row["sender_name"],
            "avatar_color": row["sender_color"],
        },
        "type": row["type"],
        "content": "" if deleted else row["content"],
        "deleted": deleted,
        "created_at": iso(row["created_at"]),
    }


def get_message(c, message_id: int) -> dict | None:
    row = c.execute(MSG_SELECT + " WHERE m.id = %s", (message_id,)).fetchone()
    return serialize_message(row) if row else None


def room_member_ids(c, room_id: int) -> list[int]:
    rows = c.execute("SELECT user_id FROM room_members WHERE room_id = %s", (room_id,)).fetchall()
    return [r["user_id"] for r in rows]


def is_member(c, room_id: int, user_id: int) -> bool:
    return (
        c.execute(
            "SELECT 1 FROM room_members WHERE room_id = %s AND user_id = %s", (room_id, user_id)
        ).fetchone()
        is not None
    )


def room_summary(c, room_id: int, me_id: int) -> dict | None:
    room = c.execute("SELECT * FROM rooms WHERE id = %s", (room_id,)).fetchone()
    if not room:
        return None
    members = c.execute(
        """SELECT u.id, u.username, u.display_name, u.avatar_color, u.status_message,
                  rm.last_read_message_id
           FROM room_members rm JOIN users u ON u.id = rm.user_id
           WHERE rm.room_id = %s ORDER BY u.id""",
        (room_id,),
    ).fetchall()
    me = next((m for m in members if m["id"] == me_id), None)
    my_last_read = me["last_read_message_id"] if me else 0

    last = c.execute(MSG_SELECT + " WHERE m.room_id = %s ORDER BY m.id DESC LIMIT 1", (room_id,)).fetchone()
    unread = c.execute(
        """SELECT COUNT(*) AS n FROM messages
           WHERE room_id = %s AND id > %s AND sender_id <> %s AND deleted_at IS NULL""",
        (room_id, my_last_read, me_id),
    ).fetchone()["n"]

    if room["type"] == "direct":
        other = next((m for m in members if m["id"] != me_id), None) or (members[0] if members else None)
        name = other["display_name"] if other else "（相手なし）"
        color = other["avatar_color"] if other else "#999999"
        partner_id = other["id"] if other else None
    else:
        name = room["name"] or "グループ"
        color = "#5b8def"
        partner_id = None

    return {
        "id": room["id"],
        "type": room["type"],
        "name": name,
        "avatar_color": color,
        "partner_id": partner_id,
        "members": [
            {
                "id": m["id"],
                "display_name": m["display_name"],
                "avatar_color": m["avatar_color"],
                "last_read_message_id": m["last_read_message_id"],
            }
            for m in members
        ],
        "my_last_read_message_id": my_last_read,
        "unread_count": unread,
        "last_message": serialize_message(last) if last else None,
        "last_activity_at": iso(last["created_at"]) if last else iso(room["created_at"]),
        "created_at": iso(room["created_at"]),
    }


def list_rooms(c, me_id: int) -> list[dict]:
    ids = [r["room_id"] for r in c.execute(
        "SELECT room_id FROM room_members WHERE user_id = %s", (me_id,)
    ).fetchall()]
    rooms = [room_summary(c, rid, me_id) for rid in ids]
    rooms = [r for r in rooms if r]
    rooms.sort(key=lambda r: r["last_activity_at"] or "", reverse=True)
    return rooms
