# 手順 2: Docker Compose でアプリを起動し、ブラウザで確認する

## ゴール

- 3 つのコンテナ（db / api / web）が起動している
- ブラウザで `http://<EC2 のパブリック IP>/` を開くとログイン画面が出て、デモアカウントでログインできる
- 2 つのアカウントでログインし、メッセージがリアルタイムに届き、既読が付くことを確認する

## 2-1. 起動する

```bash
cd ~/HandsOn-3ogyqbi3tg2
docker compose up -d --build
```

初回は Docker イメージのダウンロードと React のビルドで 2〜5 分かかります。
`-d` は裏で動かすオプション、`--build` はイメージを作り直すオプションです。

## 2-2. 状態を確認する

```bash
docker compose ps
```

3 行とも `Up` になっていれば成功です。`db` は `(healthy)` と表示されます。

```
NAME           IMAGE                     STATUS                 PORTS
training-api   handson-3ogyqbi3tg2-api   Up 10 seconds          0.0.0.0:8000->8000/tcp
training-db    postgres:16-alpine        Up 30 seconds (healthy) 5432/tcp
training-web   handson-3ogyqbi3tg2-web   Up 10 seconds          0.0.0.0:80->80/tcp
```

EC2 の中から疎通を確認します。

```bash
curl http://localhost/api/health     # {"status":"ok"}
curl http://localhost/api/info       # db_ok が true なら DB にも繋がっている
```

## 2-3. ブラウザで開く

自分の PC のブラウザで次を開きます。

```
http://<EC2 のパブリック IP>/
```

> ⚠️ `https://` ではなく **`http://`** です。ブラウザが勝手に https に変えることがあるので注意。

ログイン画面が出たら、「デモアカウントでログイン」の **佐藤 あかり** を押します。
トーク一覧に「研修グループ」と「鈴木 けんた」が出れば、Web → API → DB の経路が通っています。

### 2 人目でログインして、リアルタイムと既読を確かめる

1. **別のブラウザ**（Chrome と Safari など）か**シークレットウィンドウ**で同じ URL を開く
   （同じブラウザの別タブだとログイン情報を共有してしまうので注意）
2. **鈴木 けんた** でログインし、「佐藤 あかり」とのトークを開く
3. あかり側でも「鈴木 けんた」とのトークを開いておく
4. けんた側で文字を打つと、あかり側に「鈴木 けんた が入力中」と出る
5. Enter で送信すると、あかり側に即座に吹き出しが出る
6. あかり側がそのトークを開いていれば、けんた側の吹き出しの横に **既読** が付く
7. 😊 ボタンでスタンプ、🖼️ ボタンで画像も送ってみる
8. 自分の吹き出しにマウスを乗せて「⋯」→「送信取消」で取り消すと、相手側も「送信を取り消しました」になる
9. 「研修グループ」にけんたが投稿し、あかりが開くと「既読 1」、みおも開くと「既読 2」になる

> 💡 この「既読」は、DB の `room_members.last_read_message_id`（誰がどこまで読んだか）を
> API が WebSocket で全員に配ることで実現しています。

## 2-4. 中を見てみる（余裕があれば）

```bash
# API のログ
docker compose logs -f api

# DB に直接入って SQL を打つ
docker compose exec db psql -U app -d appdb
appdb=# SELECT id, room_id, sender_id, type, left(content, 30) FROM messages ORDER BY id DESC LIMIT 10;
appdb=# SELECT * FROM room_members;     -- 既読位置 (last_read_message_id)
appdb=# \q

# FastAPI の自動ドキュメント (ブラウザ)
http://<EC2 のパブリック IP>:8000/docs
```

## 困ったときは

| 症状 | 確認すること |
|---|---|
| ブラウザで開けない（タイムアウト） | セキュリティグループで 80 番が開いているか。`http://` になっているか |
| ログインボタンを押しても反応がない / エラー | `docker compose ps` で api が Up か。`docker compose logs api` にエラーが無いか |
| ログインはできるがメッセージが届かない | 左下が「● 接続中」になっているか。なっていなければ WebSocket が繋がっていない。`docker compose logs web` を確認 |
| ログイン画面で「ユーザー名またはパスワードが違います」 | デモアカウントのパスワードは `password`。DB を作り直したい時は `docker compose down -v` |
| `permission denied while trying to connect to the Docker daemon` | 手順 1 の再ログインをしていない。`exit` して再接続 |
| `port is already allocated` | 他のコンテナが同じポートを使っている。`docker ps -a` で確認し `docker rm -f <名前>` |

## 次のステップ

- 手順 3: 画面を S3 に載せる → [03_s3_hosting.md](03_s3_hosting.md)
- 手順 4: 研修生全員でチャットする（共有 DynamoDB に切り替え） → [04_shared_chat_dynamodb.md](04_shared_chat_dynamodb.md)

## 停止と片付け

```bash
docker compose down       # 停止。DB のデータは残る
docker compose down -v    # 停止 + DB のデータも削除（初期状態に戻したいとき）
```

## チェックポイント ✅

- [ ] `docker compose ps` で 3 つとも Up
- [ ] ブラウザで画面が表示され、API / DB ともに OK
- [ ] メッセージを追加して再読み込みしても残っている
