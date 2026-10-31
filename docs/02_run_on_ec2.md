# 手順 2: Docker Compose でアプリを起動し、ブラウザで確認する

## ゴール

- 3 つのコンテナ（db / api / web）が起動している
- ブラウザで `http://<EC2 のパブリック IP>/` を開くと画面が表示され、「API: OK」「データベース: OK」になる
- 画面からメッセージを追加すると DB に保存される

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
curl http://localhost/api/messages   # 初期データ 2 件の JSON
```

## 2-3. ブラウザで開く

自分の PC のブラウザで次を開きます。

```
http://<EC2 のパブリック IP>/
```

> ⚠️ `https://` ではなく **`http://`** です。ブラウザが勝手に https に変えることがあるので注意。

画面に次が表示されれば完了です。

- 接続状況: **API サーバー OK**、**データベース OK**
- メッセージ一覧に「システム」「講師」の 2 件
- フォームから送信すると一覧に追加され、再読み込みしても残っている

## 2-4. 中を見てみる（余裕があれば）

```bash
# API のログ
docker compose logs -f api

# DB に直接入って SQL を打つ
docker compose exec db psql -U app -d appdb
appdb=# SELECT * FROM messages;
appdb=# \q

# FastAPI の自動ドキュメント (ブラウザ)
http://<EC2 のパブリック IP>:8000/docs
```

## 困ったときは

| 症状 | 確認すること |
|---|---|
| ブラウザで開けない（タイムアウト） | セキュリティグループで 80 番が開いているか。`http://` になっているか |
| 画面は出るが「API: NG」 | `docker compose ps` で api が Up か。`docker compose logs api` にエラーが無いか |
| 「データベース: NG」 | `docker compose logs db`。`docker compose down -v` して作り直す |
| `permission denied while trying to connect to the Docker daemon` | 手順 1 の再ログインをしていない。`exit` して再接続 |
| `port is already allocated` | 他のコンテナが同じポートを使っている。`docker ps -a` で確認し `docker rm -f <名前>` |

## 停止と片付け

```bash
docker compose down       # 停止。DB のデータは残る
docker compose down -v    # 停止 + DB のデータも削除（初期状態に戻したいとき）
```

## チェックポイント ✅

- [ ] `docker compose ps` で 3 つとも Up
- [ ] ブラウザで画面が表示され、API / DB ともに OK
- [ ] メッセージを追加して再読み込みしても残っている
