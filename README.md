# Talk - 研修用チャットアプリ（EC2 + Docker Compose + S3）

EC2（Ubuntu）上で Docker Compose を使って 3 層のチャットアプリを起動し、ブラウザから使えることを確認する研修用の教材です。
後半では画面（React のビルド成果物）を S3 の静的ウェブサイトホスティングに載せ、EC2 上の API と連携させます。

研修用ですが、アプリ本体は既読やスタンプなど普段使っているチャットと同じ機能を一通り持たせています。

## 機能

| 機能 | 内容 |
|---|---|
| ログイン / 新規登録 | ユーザー名 + パスワード。デモアカウント 3 名を同梱 |
| 1:1 トーク / グループトーク | 相手を選んで開始。同じ相手との 1:1 は 1 つに集約 |
| リアルタイム配信 | WebSocket で即時反映。切断時は自動再接続して再同期 |
| 既読 | 1:1 では「既読」、グループでは「既読 N」を自分の吹き出しに表示 |
| スタンプ | 4 パック 48 種。吹き出しなしの大きな表示 |
| 画像送信 | JPEG / PNG / GIF / WebP、5MB まで。タップで拡大 |
| 送信取消 | 自分のメッセージを取り消すと相手側も「送信を取り消しました」に変わる |
| 入力中表示 | 相手が入力していると「〇〇 が入力中」とドットが出る |
| オンライン表示 | アバターの緑ドット、グループは「N 人がオンライン」 |
| 未読バッジ | トーク一覧の件数バッジとタブのタイトル `(N) チャット` |
| 日付区切り / 連続投稿のまとめ | LINE と同じ見た目のルール |
| ステータスメッセージ | 自分の名前の下をクリックして編集 |
| レスポンシブ | スマホ幅では一覧とトークを切り替える 1 カラム表示 |
| S3 用ファイル出力 | 左下のボタンから、API 接続先を書き込んだ zip をダウンロード |
| 保存先の切り替え | 設定画面で「ローカル（PostgreSQL）」と「共有（DynamoDB）」を切り替え。共有では研修生全員で同じトークが使える |

## 2 つの保存先モード

| モード | 保存先 | 用途 | リアルタイム配信 |
|---|---|---|---|
| ローカル（既定） | 自分の EC2 の PostgreSQL | 研修前半。デモアカウント付き | WebSocket |
| 共有 | 講師が用意した DynamoDB テーブル（全員共通） | 研修後半。全員でチャット | 同じ EC2 内は WebSocket、他の EC2 の書き込みは 2.5 秒ごとのポーリング |

切り替えはアプリ左下の設定（歯車のアイコン）から行い、設定は自分の EC2 の PostgreSQL（`app_settings`）に保存されます。
講師は [scripts/create_dynamodb_table.sh](scripts/create_dynamodb_table.sh) でテーブルを作り、研修生の EC2 の IAM ロールに [docs/iam_dynamodb_policy.json](docs/iam_dynamodb_policy.json) を付けます。
テーブル設計は [docs/04_shared_chat_dynamodb.md](docs/04_shared_chat_dynamodb.md) を参照してください。

## 構成

```
【前半】EC2 で全部動かす
  ブラウザ ──:80──> web (Nginx + React) ──/api, /api/ws, /uploads──> api (FastAPI) ──> db (PostgreSQL)
                    └──────────────────── すべて EC2 上の Docker コンテナ ────────────────────┘

【後半】画面だけ S3 に移す
  ブラウザ ──> S3 静的ホスティング (React の dist + config.js)
     └──────:8000──> EC2 の api (FastAPI / WebSocket) ──> db (PostgreSQL)   ※ CORS が必要
```

| サービス | 技術 | 役割 |
|---|---|---|
| `web` | Nginx 1.27 + React 18 / Vite 5 | 画面の配信。`/api/*`（WebSocket 含む）と `/uploads/*` を api へ中継 |
| `api` | Python 3.12 + FastAPI + psycopg 3 | REST API と WebSocket。画像はボリュームに保存 |
| `db`  | PostgreSQL 16 | ユーザー・ルーム・メッセージ・既読位置。初回起動時に `db/init/*.sql` でスキーマ作成 |

## ディレクトリ

```
.
├── docker-compose.yml      # 3 サービスの定義
├── .env.example            # 環境変数サンプル
├── api/                    # FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py         # アプリ本体・WebSocket エンドポイント
│       ├── routes_auth.py  # ログイン・登録・プロフィール・ユーザー検索
│       ├── routes_rooms.py # ルーム・メッセージ・既読・送信取消・画像
│       ├── routes_settings.py  # 保存先の参照・接続テスト・切り替え
│       ├── settings.py     # 設定の保存と有効なストレージの提供
│       ├── storage_base.py     # ストレージ層のインターフェース
│       ├── storage_postgres.py # ローカル実装 (PostgreSQL)
│       ├── storage_dynamodb.py # 共有実装 (DynamoDB シングルテーブル)
│       ├── ids.py          # ULID
│       ├── services.py     # PostgreSQL 用の共通クエリと JSON 変換
│       ├── ws.py           # WebSocket 接続管理
│       ├── auth.py         # パスワードハッシュとセッション
│       ├── db.py           # 接続プール
│       └── seed.py         # デモデータ
├── web/                    # React + Vite + Nginx
│   ├── Dockerfile          # マルチステージ (node でビルド → nginx で配信)
│   ├── nginx.conf          # WebSocket 中継を含む
│   ├── public/config.js    # API 接続先の実行時設定 (S3 ではこれだけ差し替える)
│   └── src/
│       ├── App.jsx         # 状態管理・WebSocket イベント処理
│       ├── api.js          # REST / WebSocket クライアント
│       ├── stickers.js     # スタンプパック定義
│       └── components/     # Login, Sidebar, ChatRoom, MessageBubble, StickerPicker, NewRoomDialog, S3Export, Avatar
├── db/init/01_schema.sql   # テーブル定義
├── scripts/
│   ├── setup_ec2.sh        # Ubuntu に Docker / Compose / AWS CLI を入れる
│   ├── build_for_s3.sh     # S3 用ファイルを web/dist に出力 (起動中コンテナから取り出す)
│   ├── create_dynamodb_table.sh  # 講師用: 共有テーブルの作成
│   └── deploy_to_s3.sh     # バケット作成・公開設定・アップロード
└── docs/
    ├── 01_ec2_setup.md     # 研修生向け: EC2 作成 〜 Docker インストール
    ├── 02_run_on_ec2.md    # 研修生向け: アプリ起動 〜 ブラウザ確認
    ├── 03_s3_hosting.md    # 研修生向け: S3 ホスティング
    ├── 04_shared_chat_dynamodb.md  # 研修生向け: 共有 DynamoDB に切り替えて全員でチャット
    ├── iam_dynamodb_policy.json    # EC2 ロールに付ける DynamoDB 権限
    └── instructor_notes.md # 講師向け: チェックポイントとつまずきやすい点
```

## クイックスタート（EC2 上）

```bash
# 0. 教材を取得
git clone https://github.com/fricton-dev/HandsOn-3ogyqbi3tg2.git
cd HandsOn-3ogyqbi3tg2

# 1. Docker のインストール (実行後いちど exit して再ログイン)
bash scripts/setup_ec2.sh

# 2. 起動
docker compose up -d --build

# 3. 確認
docker compose ps
curl http://localhost/api/health      # {"status":"ok"} が返れば OK
```

ブラウザで `http://<EC2 のパブリック IP>/` を開き、デモアカウントでログインします。

| ユーザー名 | 表示名 | パスワード |
|---|---|---|
| `akari` | 佐藤 あかり | `password` |
| `kenta` | 鈴木 けんた | `password` |
| `mio`   | 田中 みお   | `password` |

別のブラウザ（またはシークレットウィンドウ）で別のアカウントにログインすると、既読やリアルタイム配信を体験できます。

## S3 ホスティング用ファイルの出し方

API の接続先は `config.js` で**実行時**に決まるので、S3 用に再ビルドする必要はありません。

- 方法 A（画面から）: 左下のダウンロードのアイコンを押し、API の接続先を確認して「zip をダウンロード」。
  解凍した中身をそのまま S3 バケットにアップロードします。
- 方法 B（EC2 のターミナルから）:
  ```bash
  bash scripts/build_for_s3.sh http://<EC2 のパブリック IP>:8000   # web/dist に出力
  bash scripts/deploy_to_s3.sh <バケット名>                        # バケット作成〜アップロード
  ```

詳しくは [docs/03_s3_hosting.md](docs/03_s3_hosting.md) を参照してください。

## API

| メソッド | パス | 内容 |
|---|---|---|
| POST | `/api/auth/signup` | 新規登録 `{username, display_name, password}` |
| POST | `/api/auth/login` | ログイン → `{token, user}` |
| POST | `/api/auth/logout` | ログアウト |
| GET / PATCH | `/api/me` | 自分のプロフィール取得・更新 |
| GET | `/api/users?q=` | ユーザー検索 |
| GET / POST | `/api/rooms` | 自分のルーム一覧 / ルーム作成 `{type, member_ids, name}` |
| GET | `/api/rooms/{id}` | ルーム詳細（メンバーごとの既読位置を含む） |
| GET | `/api/rooms/{id}/messages?before=&after=&limit=` | メッセージ取得（`before` で古い方へ、`after` で新着のみ） |
| POST | `/api/rooms/{id}/messages` | 送信 `{type: "text"\|"sticker", content}` |
| POST | `/api/rooms/{id}/images` | 画像送信（multipart `file`） |
| POST | `/api/rooms/{id}/read` | 既読位置の更新 `{message_id}` |
| DELETE | `/api/rooms/{id}/messages/{mid}` | 送信取消 |
| GET | `/api/settings/public` | 現在の保存先モード（ログイン不要） |
| GET / PUT | `/api/settings` | 保存先の設定取得・保存（保存時に接続確認） |
| POST | `/api/settings/test` | 保存せずに接続テスト |
| WS | `/api/ws?token=` | イベント配信: `message` `message_deleted` `read` `typing` `presence` `room_created` |
| GET | `/api/health`, `/api/info` | 生存確認、DB バージョン、接続中ユーザー数 |

認証は `Authorization: Bearer <token>` ヘッダ。FastAPI の自動ドキュメントは `http://<EC2 の IP>:8000/docs`。

### 既読の仕組み

「このメッセージ ID まで読んだ」を人ごとに 1 つ持ちます（PostgreSQL は `room_members.last_read_message_id`、DynamoDB は `MEMBER#` 項目の同名属性）。
ID は PostgreSQL では連番、DynamoDB では ULID で、どちらも大小比較が時系列順になります。
自分の吹き出しの既読人数は「自分以外のメンバーのうち、`last_read_message_id >= そのメッセージ ID` の人数」です。
ルームを開いたとき・開いている間に新着が来たときに `POST /read` を送り、サーバーが WebSocket でメンバー全員に `read` イベントを配ります。

## よく使うコマンド

```bash
docker compose up -d --build   # 起動 (イメージも作り直す)
docker compose ps              # 状態確認
docker compose logs -f api     # API のログを追う
docker compose down            # 停止 (DB データ・画像は残る)
docker compose down -v         # 停止 + DB データ・画像も削除 (スキーマ変更時はこれで作り直す)
docker compose exec db psql -U app -d appdb -c 'SELECT id, room_id, sender_id, type, left(content, 30) FROM messages ORDER BY id DESC LIMIT 10;'
```

## ローカル PC で試す場合

Docker Desktop が入っていれば同じコマンドで動きます。
80 番や 8000 番が使われている場合は `docker-compose.yml` の `ports` の左側の数字を変えてください。
