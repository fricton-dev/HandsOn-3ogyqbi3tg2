"""ローカルモード: PostgreSQL 実装。"""
import secrets
from datetime import datetime, timedelta, timezone

from . import auth, db, services
from .storage_base import ConflictError, NotFoundError

SESSION_DAYS = 30


def _int(v, what="ID"):
    try:
        return int(v)
    except (TypeError, ValueError):
        raise NotFoundError(f"{what} が不正です")


class PostgresStorage:
    name = "postgres"

    # ---- 稼働確認 ----
    def ping(self) -> dict:
        with db.conn() as c:
            c.execute("SELECT 1")
        return {"ok": True, "detail": "PostgreSQL に接続できました"}

    def info(self) -> dict:
        with db.conn() as c:
            row = c.execute("SELECT version()").fetchone()
        return {"backend": "postgres", "db_version": row["version"]}

    # ---- ユーザー ----
    def create_user(self, username, display_name, password_hash, avatar_color):
        with db.conn() as c:
            if c.execute("SELECT 1 FROM users WHERE username = %s", (username,)).fetchone():
                raise ConflictError("そのユーザー名は既に使われています")
            row = c.execute(
                """INSERT INTO users (username, display_name, password_hash, avatar_color)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, username, display_name, avatar_color, status_message""",
                (username, display_name, password_hash, avatar_color),
            ).fetchone()
        return services.serialize_user(row)

    def get_user_with_hash(self, username):
        with db.conn() as c:
            row = c.execute("SELECT * FROM users WHERE username = %s", (username,)).fetchone()
        return dict(row) if row else None

    def get_user(self, user_id):
        with db.conn() as c:
            row = c.execute(
                "SELECT id, username, display_name, avatar_color, status_message FROM users WHERE id = %s",
                (_int(user_id),),
            ).fetchone()
        return services.serialize_user(row) if row else None

    def update_user(self, user_id, display_name, status_message):
        with db.conn() as c:
            row = c.execute(
                """UPDATE users SET display_name = COALESCE(%s, display_name),
                                    status_message = COALESCE(%s, status_message)
                   WHERE id = %s RETURNING id, username, display_name, avatar_color, status_message""",
                (display_name, status_message, _int(user_id)),
            ).fetchone()
        return services.serialize_user(row)

    def search_users(self, q, exclude_id):
        with db.conn() as c:
            rows = c.execute(
                """SELECT id, username, display_name, avatar_color, status_message FROM users
                   WHERE id <> %s AND (display_name ILIKE %s OR username ILIKE %s)
                   ORDER BY display_name LIMIT 100""",
                (_int(exclude_id), f"%{q}%", f"%{q}%"),
            ).fetchall()
        return [services.serialize_user(r) for r in rows]

    # ---- セッション ----
    def create_session(self, user_id):
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        with db.conn() as c:
            c.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
                      (token, _int(user_id), expires))
        return token

    def delete_session(self, token):
        with db.conn() as c:
            c.execute("DELETE FROM sessions WHERE token = %s", (token,))

    def user_from_token(self, token):
        if not token:
            return None
        with db.conn() as c:
            row = c.execute(
                """SELECT u.id, u.username, u.display_name, u.avatar_color, u.status_message
                   FROM sessions s JOIN users u ON u.id = s.user_id
                   WHERE s.token = %s AND s.expires_at > NOW()""",
                (token,),
            ).fetchone()
        return services.serialize_user(row) if row else None

    # ---- ルーム ----
    def list_rooms(self, me_id):
        with db.conn() as c:
            return services.list_rooms(c, _int(me_id))

    def room_summary(self, room_id, me_id):
        with db.conn() as c:
            return services.room_summary(c, _int(room_id), _int(me_id))

    def is_member(self, room_id, user_id):
        try:
            rid, uid = _int(room_id), _int(user_id)
        except NotFoundError:
            return False
        with db.conn() as c:
            return services.is_member(c, rid, uid)

    def room_member_ids(self, room_id):
        with db.conn() as c:
            return services.room_member_ids(c, _int(room_id))

    def create_room(self, room_type, name, member_ids, creator):
        member_ids = sorted({_int(m) for m in member_ids} | {_int(creator["id"])})
        with db.conn() as c:
            found = c.execute("SELECT COUNT(*) AS n FROM users WHERE id = ANY(%s)", (member_ids,)).fetchone()["n"]
            if found != len(member_ids):
                raise NotFoundError("存在しないユーザーが含まれています")
            if room_type == "direct":
                existing = c.execute(
                    """SELECT r.id FROM rooms r WHERE r.type = 'direct'
                       AND (SELECT array_agg(user_id ORDER BY user_id) FROM room_members WHERE room_id = r.id) = %s::int[]
                       LIMIT 1""",
                    (member_ids,),
                ).fetchone()
                if existing:
                    return existing["id"]
            room = c.execute(
                "INSERT INTO rooms (type, name, created_by) VALUES (%s, %s, %s) RETURNING id",
                (room_type, name, creator["id"]),
            ).fetchone()
            for uid in member_ids:
                c.execute("INSERT INTO room_members (room_id, user_id) VALUES (%s, %s)", (room["id"], uid))
            if room_type == "group":
                self._insert(c, room["id"], creator["id"], "system", f"{creator['display_name']}がグループを作成しました")
            c.commit()
            return room["id"]

    # ---- メッセージ ----
    def list_messages(self, room_id, before, after, limit):
        rid = _int(room_id)
        with db.conn() as c:
            if after:
                rows = c.execute(
                    services.MSG_SELECT + " WHERE m.room_id = %s AND m.id > %s ORDER BY m.id ASC LIMIT %s",
                    (rid, _int(after), limit),
                ).fetchall()
                return [services.serialize_message(r) for r in rows], len(rows) == limit
            if before:
                rows = c.execute(
                    services.MSG_SELECT + " WHERE m.room_id = %s AND m.id < %s ORDER BY m.id DESC LIMIT %s",
                    (rid, _int(before), limit),
                ).fetchall()
            else:
                rows = c.execute(
                    services.MSG_SELECT + " WHERE m.room_id = %s ORDER BY m.id DESC LIMIT %s", (rid, limit)
                ).fetchall()
        rows.reverse()
        return [services.serialize_message(r) for r in rows], len(rows) == limit

    @staticmethod
    def _insert(c, room_id, sender_id, mtype, content):
        row = c.execute(
            "INSERT INTO messages (room_id, sender_id, type, content) VALUES (%s, %s, %s, %s) RETURNING id",
            (room_id, sender_id, mtype, content),
        ).fetchone()
        c.execute(
            """UPDATE room_members SET last_read_message_id = GREATEST(last_read_message_id, %s)
               WHERE room_id = %s AND user_id = %s""",
            (row["id"], room_id, sender_id),
        )
        return services.get_message(c, row["id"])

    def insert_message(self, room_id, sender, mtype, content):
        with db.conn() as c:
            msg = self._insert(c, _int(room_id), _int(sender["id"]), mtype, content)
            c.commit()
        return msg

    def get_message(self, room_id, message_id):
        with db.conn() as c:
            msg = services.get_message(c, _int(message_id))
        return msg if msg and msg["room_id"] == _int(room_id) else None

    def mark_read(self, room_id, user_id, message_id):
        with db.conn() as c:
            row = c.execute(
                """UPDATE room_members SET last_read_message_id = GREATEST(last_read_message_id, %s)
                   WHERE room_id = %s AND user_id = %s RETURNING last_read_message_id""",
                (_int(message_id), _int(room_id), _int(user_id)),
            ).fetchone()
            c.commit()
        return row["last_read_message_id"] if row else None

    def unsend_message(self, room_id, message_id, user_id):
        with db.conn() as c:
            row = c.execute("SELECT room_id, sender_id, deleted_at FROM messages WHERE id = %s",
                            (_int(message_id),)).fetchone()
            if not row or row["room_id"] != _int(room_id) or row["sender_id"] != _int(user_id):
                return None
            if row["deleted_at"] is None:
                c.execute("UPDATE messages SET deleted_at = NOW() WHERE id = %s", (_int(message_id),))
                c.commit()
            return services.get_message(c, _int(message_id))

    # ---- 初期データ ----
    def seed_demo(self):
        from . import seed
        seed.seed_if_empty()
