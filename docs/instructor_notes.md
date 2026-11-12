# 講師向けメモ

## 研修の流れ（目安 3 時間）

| 時間 | 内容 | チェックポイント |
|---|---|---|
| 0:00–0:40 | EC2 作成、SSH、Docker インストール | `docker compose version` が出る |
| 0:40–1:30 | `docker compose up`、2 アカウントでログインして既読・スタンプ・画像を試す、ログや DB を覗く | 2 ブラウザ間でリアルタイムに届き既読が付く |
| 1:30–1:45 | 休憩 / 進捗合わせ | |
| 1:45–2:30 | S3 ホスティング、CORS の説明、動作確認 | S3 の URL で画面が出てログインできる |
| 2:30–3:10 | 共有 DynamoDB に切り替えて全員でチャット | 全員が 1 つのグループで会話できる |
| 3:10–3:30 | 片付け、振り返り | リソース削除 |

## 事前準備

### 共有チャット用 DynamoDB テーブル（手順 4 用）

```bash
bash scripts/create_dynamodb_table.sh handson-chat ap-northeast-1
bash scripts/create_image_bucket.sh handson-chat-images ap-northeast-1   # 共有モードの画像置き場 (非公開のまま)
```

- 研修生の EC2 に付ける IAM ロールに `docs/iam_dynamodb_policy.json` の内容を追加する（Resource をテーブルの ARN とバケット名に）
- 研修生に伝えるもの: テーブル名、リージョン、画像用バケット名
- 研修当日の開始前にテーブルを空にしたい場合は、削除して作り直すのが早い（`aws dynamodb delete-table --table-name handson-chat`）
- 講師自身も先に 1 アカウント作り、「全員」グループを作っておくと誘導しやすい

- 研修生ごとの IAM ユーザー（EC2 / S3 / IAM ロールのパススルー権限）
- EC2 用 IAM ロール `training-ec2-s3-role`（`AmazonS3FullAccess`）を先に作っておくと 3-2 の権限エラーがなくなる
- 教材の配布方法（Git リポジトリ or zip）。Git の場合は `git clone` の URL を資料に書く
- 動作確認済みのリージョン・AMI・インスタンスタイプ（`ap-northeast-1` / Ubuntu Server 24.04 LTS / `t3.small`）

## つまずきやすいポイントと対処

### 手順 1

| 症状 | 原因 | 対処 |
|---|---|---|
| `Permission denied (publickey)` | `.pem` の権限 / ユーザー名違い | `chmod 400`、ユーザーは `ubuntu`（`ec2-user` ではない） |
| SSH タイムアウト | SG の 22 番が「マイ IP」で、受講者の IP が変わった | SG を 0.0.0.0/0 に一時変更、または Instance Connect |
| `docker: permission denied` | 再ログインしていない | `exit` → 再接続。急ぐなら `newgrp docker` |
| `apt-get` が `Could not get lock` で止まる | 起動直後の自動アップデート (unattended-upgrades) が走っている | 1〜2 分待ってから再実行 |
| `aws: command not found` | Ubuntu には AWS CLI が入っていない | `setup_ec2.sh` が入れる。再ログインしていないなら `exit` → 再接続 |

### 手順 2

| 症状 | 原因 | 対処 |
|---|---|---|
| ビルドが異常に遅い / OOM | `t3.micro`（1 GiB）で React ビルド | `t3.small` 以上を推奨。micro なら swap を作る |
| ブラウザで開けない | `https://` に自動補正されている | アドレスバーで `http://` を明示 |
| ログインできない | api コンテナが落ちている | `docker compose logs api`。DB 起動待ちは接続プールのリトライと healthcheck で吸収している |
| メッセージが届かない（左下が接続中にならない） | WebSocket が中継されていない | `web/nginx.conf` の `Upgrade` ヘッダ設定を確認。EC2 の前に ALB などを挟んだ場合も要注意 |
| 2 人目のログインで 1 人目が追い出される | 同じブラウザの別タブで試している（localStorage を共有） | 別ブラウザかシークレットウィンドウを使う |
| 画像が送れない | 5MB 超、または対応形式外 | API 側で 5MB・JPEG/PNG/GIF/WebP に制限している |
| `port is already allocated` | 前回のコンテナが残っている | `docker compose down` または `docker ps -a` で掃除 |

### 手順 3

| 症状 | 原因 | 対処 |
|---|---|---|
| `AccessDenied` / `Unable to locate credentials` | IAM ロール未付与 | ロールを付ける（反映に数十秒） |
| `BucketAlreadyExists` | バケット名が世界で重複 | 名前に日付や乱数を追加 |
| S3 の画面でログインできない | `config.js` の IP 間違い、SG の 8000 番未開放、API 停止 | 開発者ツールのネットワークタブで宛先 IP を確認 → `config.js` を直して再アップロード → SG → `docker compose ps` |
| S3 で 404 / 真っ白 | フォルダごとアップロードして `index.html` がルートに無い | バケット直下に `index.html` と `assets/` が来るように再アップロード |
| CORS エラー（開発者ツールに表示） | `CORS_ORIGINS` を絞って S3 の URL と不一致 | `*` に戻すか、`http://` を含めた正確なオリジンを指定 |
| 403 で `index.html` が出ない | パブリックアクセスブロックが残っている | コンソールで「ブロックパブリックアクセス」を確認 |
| Mixed Content エラー | S3 を https で開き API が http | S3 は http で開く |

### 手順 4

| 症状 | 原因 | 対処 |
|---|---|---|
| 接続テストで「認証情報がありません」 | EC2 に IAM ロールが無い | ロールを付ける。反映まで 1 分ほど。詳細設定のアクセスキーは最後の手段 |
| 「権限または認証情報の問題」(AccessDenied) | ロールのポリシーにテーブルの権限が無い / ARN 違い | `iam_dynamodb_policy.json` の Resource を確認 |
| 「テーブルが見つかりません」 | 名前かリージョンの入力ミス | 講師が伝えた値と突き合わせる |
| 新規登録で「既に使われています」 | 他の研修生と同じユーザー名 | 名前に自分の識別子を入れる |
| 相手のメッセージが出るまで数秒かかる | 仕様（ポーリング 2.5 秒） | 「なぜ即時でないのか」を説明する好機 |
| 画像ボタンが押せない / 「画像用 S3 バケットを指定してください」 | 設定画面でバケット名が空 | バケット名を入れて保存し直す |
| 接続テストで「S3 バケットが見つかりません」「権限」 | バケット名違い / ロールに s3:PutObject 等が無い | `iam_dynamodb_policy.json` の SharedChatImages を確認 |
| 共有モードの画像が壊れて表示される | 送信側の EC2 だけバケット未設定で、ローカルのパスが保存された | 送信側で設定を直してから送り直す |
| 入力中 / オンラインが出ない | 仕様（WebSocket は同じ EC2 内のみ） | 同上 |

## 説明で強調したいこと

- **パーティションキーの選び方**: 「このルームの最新 N 件」が最頻のアクセスだからルーム ID を PK に、ソートキーに時刻順の ULID を置く。ユーザー ID や日付を PK にすると何が困るかを問いかける
- **シングルテーブル設計**: 1 テーブルにユーザー・ルーム・メッセージが同居している。コンソールの「項目を探索」で `pk` の種類を見せる
- **メタデータは DynamoDB、実ファイルは S3**: ローカルモードでは画像が各 EC2 のディスクに取り残されて他の人に見えない。共有モードでは S3 に置き、API が取り出して返すのでバケットは非公開のまま。「状態はどこにあるか」の話とつなげる
- **WebSocket の限界とポーリング**: API のメモリにある接続一覧は EC2 をまたげない。共有モードがポーリングになっている理由と、本番での選択肢（API Gateway WebSocket / DynamoDB Streams）

- **REST と WebSocket の役割分担**: 送信・取得は REST（HTTP）、「届いた」「読んだ」「入力中」の通知は WebSocket。片方だけでは LINE のような体験にならないことを、入力中表示で体感させる
- **既読の実装はシンプル**: 「誰がどこまで読んだか」を人ごとに 1 つの数字で持つだけ。`SELECT * FROM room_members` を見せると腑に落ちる
- **状態はどこにあるか**: メッセージ・既読は DB、WebSocket の接続一覧は API のメモリ、画像はボリューム。`docker compose down` と `down -v` で何が消えるかと結びつける

- **コンテナ間の名前解決**: Nginx の `proxy_pass http://api:8000` と API の `DATABASE_URL=...@db:5432` は、Compose がサービス名で DNS を用意しているから通る。`localhost` ではない点を強調
- **ポート公開の意味**: `ports:` を書いたサービスだけが EC2 の外から見える。`db` は書いていないので外から 5432 で繋げない（= 安全）
- **設定の外出し**: 画面の API 接続先は `config.js` に外出ししてあるので、IP が変わっても再ビルド不要でファイル 1 つの差し替えで済む。「ビルド成果物と環境設定を分ける」という考え方の入口として触れる
- **zip 書き出しボタンの仕組み**: 自分自身の HTML/JS/CSS をブラウザが fetch し、`config.js` を生成して zip にしている。ツール無しでも S3 に持っていけるようにするための研修用の仕掛けで、業務では CI でビルドして `aws s3 sync` する
- **同一オリジンと CORS**: 手順 2 で CORS が不要だった理由（Nginx が中継していたから）と、手順 3 で必要になった理由
- **S3 公開設定は研修用の簡易版**: 実務では CloudFront + OAC（Origin Access Control）でバケットは非公開にする

## 発展課題（時間が余った受講者向け）

1. `.env` を作って `POSTGRES_PASSWORD` を変え、`docker compose down -v && up -d` で反映されることを確認
2. `web/src/stickers.js` にスタンプパックを 1 つ追加して再ビルド
3. メッセージへのリアクション（いいね など）を API と画面に追加する
4. CloudFront を S3 の前に置いて https 化する（WebSocket は `wss://` にする必要があり、API 側も TLS が要る点に気づかせる）
5. API 側も ECS / App Runner に移してみる（EC2 を無くす。WebSocket の接続一覧がメモリにあるため複数台にすると壊れることを議論する）

## コスト目安（ap-northeast-1）

- `t3.small` 1 台: 約 0.027 USD/時 → 3 時間で 0.1 USD 弱
- S3: 数 MB なのでほぼ 0
- 終了後に **EC2 の終了・S3 バケットの削除**を必ず確認すること（放置が一番のコスト）
