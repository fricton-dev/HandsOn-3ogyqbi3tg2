-- 初回起動時に PostgreSQL が自動実行する初期化SQL
CREATE TABLE IF NOT EXISTS messages (
    id         SERIAL PRIMARY KEY,
    author     VARCHAR(50)  NOT NULL,
    body       VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

INSERT INTO messages (author, body) VALUES
    ('システム', 'ようこそ！この行は PostgreSQL から取得されています。'),
    ('講師',     'この画面が見えていれば Web → API → DB の経路がすべて通っています。');
