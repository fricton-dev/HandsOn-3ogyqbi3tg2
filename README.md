# AWS 研修サンプルアプリ（EC2 + Docker Compose + S3）

EC2 上で Docker Compose を使って 3 層アプリを起動し、ブラウザから表示できることを確認する研修用の教材です。
後半では、画面（React のビルド成果物）を S3 の静的ウェブサイトホスティングに載せ、EC2 上の API と連携させます。

## 構成

```
【前半】EC2 で全部動かす
  ブラウザ ──:80──> web (Nginx + React) ──/api──> api (FastAPI) ──> db (PostgreSQL)
                    └──────────────── すべて EC2 上の Docker コンテナ ───────────────┘

【後半】画面だけ S3 に移す
  ブラウザ ──> S3 静的ホスティング (React の dist)
     └──────:8000──> EC2 の api (FastAPI) ──> db (PostgreSQL)   ※ CORS が必要
```

| サービス | 技術 | 役割 |
|---|---|---|
| `web` | Nginx 1.27 + React 18 / Vite 5 | 画面の配信。`/api/*` を api へ中継。右下のボタンで S3 用 zip を出力 |
| `api` | Python 3.12 + FastAPI | REST API。メッセージの一覧取得・追加 |
| `db`  | PostgreSQL 16 | データ保存。初回起動時に `db/init/*.sql` を自動実行 |

## ディレクトリ

```
.
├── docker-compose.yml      # 3 サービスの定義
├── .env.example            # 環境変数サンプル
├── api/                    # FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/main.py, db.py
├── web/                    # React + Vite + Nginx
│   ├── Dockerfile          # マルチステージ (node でビルド → nginx で配信)
│   ├── nginx.conf
│   ├── public/config.js    # API 接続先の実行時設定 (S3 ではこれだけ差し替える)
│   └── src/                # App.jsx, S3Export.jsx (右下の zip 出力パネル)
├── db/init/01_schema.sql   # テーブル作成と初期データ
├── scripts/
│   ├── setup_ec2.sh        # Amazon Linux 2023 に Docker を入れる
│   ├── build_for_s3.sh     # S3 用ファイルを web/dist に出力 (起動中コンテナから取り出す)
│   └── deploy_to_s3.sh     # バケット作成・公開設定・アップロード
└── docs/
    ├── 01_ec2_setup.md     # 研修生向け: EC2 作成 〜 Docker インストール
    ├── 02_run_on_ec2.md    # 研修生向け: アプリ起動 〜 ブラウザ確認
    ├── 03_s3_hosting.md    # 研修生向け: S3 ホスティング
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

ブラウザで `http://<EC2 のパブリック IP>/` を開くと画面が表示されます。

## S3 ホスティング用ファイルの出し方

API の接続先は `config.js` で**実行時**に決まるので、S3 用に再ビルドする必要はありません。

- **方法 A（画面から）**: 右下の「📦 S3 用ファイルを出力」→ API の接続先を確認 → 「zip をダウンロード」。
  解凍した中身をそのまま S3 バケットにアップロードします。
- **方法 B（EC2 のターミナルから）**:
  ```bash
  bash scripts/build_for_s3.sh http://<EC2 のパブリック IP>:8000   # web/dist に出力
  bash scripts/deploy_to_s3.sh <バケット名>                        # バケット作成〜アップロード
  ```

詳しくは [docs/03_s3_hosting.md](docs/03_s3_hosting.md) を参照してください。

## API エンドポイント

| メソッド | パス | 内容 |
|---|---|---|
| GET  | `/api/health`   | 生存確認（DB には触らない） |
| GET  | `/api/info`     | API ホスト名と DB バージョン |
| GET  | `/api/messages` | メッセージ一覧（DB から取得） |
| POST | `/api/messages` | メッセージ追加 `{"author": "...", "body": "..."}` |

FastAPI の自動ドキュメントは `http://<EC2 の IP>:8000/docs` で見られます。

## よく使うコマンド

```bash
docker compose up -d --build   # 起動 (イメージも作り直す)
docker compose ps              # 状態確認
docker compose logs -f api     # API のログを追う
docker compose down            # 停止 (DB データは残る)
docker compose down -v         # 停止 + DB データも削除
docker compose exec db psql -U app -d appdb -c 'SELECT * FROM messages;'   # DB を直接見る
```

## ローカル PC で試す場合

Docker Desktop が入っていれば同じコマンドで動きます。
80 番や 8000 番が使われている場合は `docker-compose.yml` の `ports` の左側の数字を変えてください。
