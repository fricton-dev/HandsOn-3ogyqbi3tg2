# 手順 1: EC2 インスタンスの作成と Docker のインストール

## ゴール

- EC2 インスタンス（Ubuntu Server 24.04 LTS）を 1 台作成し、SSH で接続できる
- Docker と Docker Compose が使える状態になっている

## 1-1. EC2 インスタンスを作成する

AWS マネジメントコンソール → EC2 → 「インスタンスを起動」

| 項目 | 設定値 |
|---|---|
| 名前 | `training-<自分の名前>` |
| AMI | **Ubuntu Server 24.04 LTS** (x86_64 または arm64 どちらでも可) |
| インスタンスタイプ | `t3.small` 推奨（`t3.micro` でも動くが React のビルドが遅い） |
| キーペア | 新規作成してダウンロード（紛失注意） |
| ネットワーク | パブリック IP の自動割り当て: **有効** |
| セキュリティグループ | 下表のインバウンドルールを作成 |
| ストレージ | 16 GiB 以上（Docker イメージを置くため） |

### セキュリティグループのインバウンドルール

| タイプ | ポート | ソース | 用途 |
|---|---|---|---|
| SSH | 22 | マイ IP | 接続用 |
| HTTP | 80 | 0.0.0.0/0 | 画面（Nginx） |
| カスタム TCP | 8000 | 0.0.0.0/0 | API（後半の S3 連携で使う） |

> 8000 番は後半まで不要ですが、あとで追加し忘れる人が多いので最初に開けておきます。

### （後半で使う）IAM ロールの付与

後半で EC2 から S3 にアップロードするため、S3 の権限を持つ IAM ロールを付けておくとスムーズです。
「高度な詳細」→「IAM インスタンスプロフィール」で、`AmazonS3FullAccess` を付けたロールを選びます。
講師がロールを用意している場合はその名前を使ってください。

## 1-2. SSH で接続する

```bash
chmod 400 ~/Downloads/<キーペア名>.pem
ssh -i ~/Downloads/<キーペア名>.pem ubuntu@<パブリック IP>
```

Windows の場合は PowerShell か、EC2 コンソールの「接続」→「EC2 Instance Connect」でも構いません。

> 注意: ユーザー名は **`ubuntu`** です（Amazon Linux の `ec2-user` ではありません）。

## 1-3. 教材を取得する

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/fricton-dev/HandsOn-3ogyqbi3tg2.git
cd HandsOn-3ogyqbi3tg2
```

## 1-4. Docker をインストールする

```bash
bash scripts/setup_ec2.sh
```

Docker 本体、Docker Compose プラグイン、AWS CLI（後半の S3 アップロードで使う）をまとめて入れます。
3〜5 分かかります。

実行が終わったら、**いちど `exit` で切断して、再度 SSH 接続**してください。
`sudo` なしで `docker` が使えるようになるにはこの再ログインが必要です。

### 確認

```bash
docker --version          # Docker version 2x.x.x
docker compose version    # Docker Compose version v2.x.x
aws --version             # aws-cli/2.x.x
docker ps                 # エラーが出ずに空の表が出れば OK
```

## 手動で入れる場合（スクリプトの中身）

Docker 公式ドキュメントの Ubuntu 向け手順と同じです。

```bash
# Docker 公式リポジトリの登録
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Docker と Compose プラグイン
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu

# AWS CLI v2
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o awscliv2.zip
unzip -q awscliv2.zip && sudo ./aws/install && rm -rf aws awscliv2.zip
```

> Ubuntu の標準リポジトリにある `docker.io` パッケージでも動きますが、バージョンが古く Compose プラグインが別扱いになるため、公式リポジトリを使います。

## チェックポイント

- [ ] `ssh` で EC2 に入れた
- [ ] `docker ps` が sudo なしで動く
- [ ] `docker compose version` が表示される
