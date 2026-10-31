-- 初回起動時に PostgreSQL が自動実行する初期化SQL (チャットアプリ)
-- 既にデータがある場合は docker compose down -v で作り直すこと

CREATE TABLE users (
    id             SERIAL PRIMARY KEY,
    username       VARCHAR(30)  NOT NULL UNIQUE,
    display_name   VARCHAR(50)  NOT NULL,
    password_hash  TEXT         NOT NULL,
    avatar_color   VARCHAR(7)   NOT NULL,
    status_message VARCHAR(100) NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE sessions (
    token      TEXT        PRIMARY KEY,
    user_id    INT         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE rooms (
    id         SERIAL PRIMARY KEY,
    type       VARCHAR(10) NOT NULL CHECK (type IN ('direct', 'group')),
    name       VARCHAR(50),
    created_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE room_members (
    room_id              INT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id              INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_read_message_id INT NOT NULL DEFAULT 0,   -- 既読管理: この ID 以下は既読
    joined_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (room_id, user_id)
);

CREATE TABLE messages (
    id         SERIAL PRIMARY KEY,
    room_id    INT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    sender_id  INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       VARCHAR(10) NOT NULL CHECK (type IN ('text', 'sticker', 'image', 'system')),
    content    TEXT NOT NULL,                      -- text: 本文 / sticker: スタンプID / image: 画像パス
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ                         -- 送信取消 (NULL 以外なら取消済み)
);
CREATE INDEX idx_messages_room ON messages (room_id, id);
CREATE INDEX idx_sessions_user ON sessions (user_id);

-- アプリ設定 (ストレージの切り替え先など)。API 起動時にも CREATE IF NOT EXISTS する
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
