# 講師向けメモ

## 研修の流れ（目安 3 時間）

| 時間 | 内容 | チェックポイント |
|---|---|---|
| 0:00–0:40 | EC2 作成、SSH、Docker インストール | `docker compose version` が出る |
| 0:40–1:30 | `docker compose up`、ブラウザ確認、ログや DB を覗く | 画面で API / DB が OK、メッセージ追加が永続化 |
| 1:30–1:45 | 休憩 / 進捗合わせ | |
| 1:45–2:40 | S3 ホスティング、CORS の説明、動作確認 | S3 の URL で画面が出て API も OK |
| 2:40–3:00 | 片付け、振り返り | リソース削除 |

## 事前準備

- 研修生ごとの IAM ユーザー（EC2 / S3 / IAM ロールのパススルー権限）
- EC2 用 IAM ロール `training-ec2-s3-role`（`AmazonS3FullAccess`）を先に作っておくと 3-2 の権限エラーがなくなる
- 教材の配布方法（Git リポジトリ or zip）。Git の場合は `git clone` の URL を資料に書く
- 動作確認済みのリージョンとインスタンスタイプ（`ap-northeast-1` / `t3.small`）

## つまずきやすいポイントと対処

### 手順 1

| 症状 | 原因 | 対処 |
|---|---|---|
| `Permission denied (publickey)` | `.pem` の権限 / ユーザー名違い | `chmod 400`、ユーザーは `ec2-user` |
| SSH タイムアウト | SG の 22 番が「マイ IP」で、受講者の IP が変わった | SG を 0.0.0.0/0 に一時変更、または Instance Connect |
| `docker: permission denied` | 再ログインしていない | `exit` → 再接続。急ぐなら `newgrp docker` |
| Compose の curl が失敗 | GitHub API のレート制限 | スクリプトは予備バージョンにフォールバックする。手動で `releases/latest/download/...` を使ってもよい |

### 手順 2

| 症状 | 原因 | 対処 |
|---|---|---|
| ビルドが異常に遅い / OOM | `t3.micro`（1 GiB）で React ビルド | `t3.small` 以上を推奨。micro なら swap を作る |
| ブラウザで開けない | `https://` に自動補正されている | アドレスバーで `http://` を明示 |
| 画面は出るが API: NG | api コンテナが落ちている | `docker compose logs api`。多くは DB 接続前のタイミング問題だが、`wait_for_db` と healthcheck で吸収している |
| `port is already allocated` | 前回のコンテナが残っている | `docker compose down` または `docker ps -a` で掃除 |

### 手順 3

| 症状 | 原因 | 対処 |
|---|---|---|
| `AccessDenied` / `Unable to locate credentials` | IAM ロール未付与 | ロールを付ける（反映に数十秒） |
| `BucketAlreadyExists` | バケット名が世界で重複 | 名前に日付や乱数を追加 |
| S3 の画面で API: NG | `config.js` の IP 間違い、SG の 8000 番未開放、API 停止 | 画面上の「API の接続先」表示で IP を確認 → `config.js` を直して再アップロード → SG → `docker compose ps` |
| S3 で 404 / 真っ白 | フォルダごとアップロードして `index.html` がルートに無い | バケット直下に `index.html` と `assets/` が来るように再アップロード |
| CORS エラー（開発者ツールに表示） | `CORS_ORIGINS` を絞って S3 の URL と不一致 | `*` に戻すか、`http://` を含めた正確なオリジンを指定 |
| 403 で `index.html` が出ない | パブリックアクセスブロックが残っている | コンソールで「ブロックパブリックアクセス」を確認 |
| Mixed Content エラー | S3 を https で開き API が http | S3 は http で開く |

## 説明で強調したいこと

- **コンテナ間の名前解決**: Nginx の `proxy_pass http://api:8000` と API の `DATABASE_URL=...@db:5432` は、Compose がサービス名で DNS を用意しているから通る。`localhost` ではない点を強調
- **ポート公開の意味**: `ports:` を書いたサービスだけが EC2 の外から見える。`db` は書いていないので外から 5432 で繋げない（= 安全）
- **設定の外出し**: 画面の API 接続先は `config.js` に外出ししてあるので、IP が変わっても再ビルド不要でファイル 1 つの差し替えで済む。「ビルド成果物と環境設定を分ける」という考え方の入口として触れる
- **右下の zip 出力ボタンの仕組み**: 自分自身の HTML/JS/CSS をブラウザが fetch し、`config.js` を生成して zip にしている。ツール無しでも S3 に持っていけるようにするための研修用の仕掛けで、業務では CI でビルドして `aws s3 sync` する
- **同一オリジンと CORS**: 手順 2 で CORS が不要だった理由（Nginx が中継していたから）と、手順 3 で必要になった理由
- **S3 公開設定は研修用の簡易版**: 実務では CloudFront + OAC（Origin Access Control）でバケットは非公開にする

## 発展課題（時間が余った受講者向け）

1. `.env` を作って `POSTGRES_PASSWORD` を変え、`docker compose down -v && up -d` で反映されることを確認
2. `api/app/main.py` に `DELETE /api/messages/{id}` を追加して再ビルド
3. CloudFront を S3 の前に置いて https 化する
4. API 側も ECS / App Runner に移してみる（EC2 を無くす）

## コスト目安（ap-northeast-1）

- `t3.small` 1 台: 約 0.027 USD/時 → 3 時間で 0.1 USD 弱
- S3: 数 MB なのでほぼ 0
- 終了後に **EC2 の終了・S3 バケットの削除**を必ず確認すること（放置が一番のコスト）
