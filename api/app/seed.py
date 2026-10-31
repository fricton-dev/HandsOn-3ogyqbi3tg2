"""初回起動時のデモデータ。ユーザーが 1 人もいない時だけ作る。"""
from . import auth, db, services

DEMO_USERS = [
    ("akari", "佐藤 あかり", "今日もがんばる☀️"),
    ("kenta", "鈴木 けんた", "研修中"),
    ("mio", "田中 みお", ""),
]
DEMO_PASSWORD = "password"


def seed_if_empty() -> None:
    with db.conn() as c:
        if c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] > 0:
            return
        ids = {}
        for username, name, status in DEMO_USERS:
            row = c.execute(
                """INSERT INTO users (username, display_name, password_hash, avatar_color, status_message)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (username, name, auth.hash_password(DEMO_PASSWORD), services.pick_color(username), status),
            ).fetchone()
            ids[username] = row["id"]

        def add_msg(room_id, sender, mtype, content):
            r = c.execute(
                "INSERT INTO messages (room_id, sender_id, type, content) VALUES (%s, %s, %s, %s) RETURNING id",
                (room_id, sender, mtype, content),
            ).fetchone()
            return r["id"]

        # グループ
        g = c.execute(
            "INSERT INTO rooms (type, name, created_by) VALUES ('group', '研修グループ', %s) RETURNING id",
            (ids["akari"],),
        ).fetchone()["id"]
        for u in ids.values():
            c.execute("INSERT INTO room_members (room_id, user_id) VALUES (%s, %s)", (g, u))
        add_msg(g, ids["akari"], "system", "佐藤 あかりがグループを作成しました")
        add_msg(g, ids["akari"], "text", "みなさん、今日の研修よろしくお願いします！")
        add_msg(g, ids["kenta"], "text", "よろしくお願いします")
        add_msg(g, ids["mio"], "sticker", "🙌")
        last_g = add_msg(g, ids["akari"], "text", "EC2 が起動したら、このチャットで教えてください")
        # 既読状態: あかり=全部, けんた=途中まで, みお=自分の投稿まで
        c.execute("UPDATE room_members SET last_read_message_id=%s WHERE room_id=%s AND user_id=%s", (last_g, g, ids["akari"]))
        c.execute("UPDATE room_members SET last_read_message_id=%s WHERE room_id=%s AND user_id=%s", (last_g - 1, g, ids["kenta"]))
        c.execute("UPDATE room_members SET last_read_message_id=%s WHERE room_id=%s AND user_id=%s", (last_g - 1, g, ids["mio"]))

        # 1:1
        d = c.execute(
            "INSERT INTO rooms (type, created_by) VALUES ('direct', %s) RETURNING id", (ids["akari"],)
        ).fetchone()["id"]
        for u in (ids["akari"], ids["kenta"]):
            c.execute("INSERT INTO room_members (room_id, user_id) VALUES (%s, %s)", (d, u))
        add_msg(d, ids["kenta"], "text", "あかりさん、docker compose up が終わりました")
        add_msg(d, ids["akari"], "text", "お疲れさまです！ブラウザで開けましたか？")
        last_d = add_msg(d, ids["kenta"], "sticker", "👍")
        c.execute("UPDATE room_members SET last_read_message_id=%s WHERE room_id=%s AND user_id=%s", (last_d, d, ids["kenta"]))
        c.execute("UPDATE room_members SET last_read_message_id=%s WHERE room_id=%s AND user_id=%s", (last_d - 1, d, ids["akari"]))
        c.commit()
