#!/usr/bin/env bash
# Ubuntu (22.04 / 24.04 LTS) に Docker, Docker Compose, AWS CLI を入れるスクリプト
# 使い方: bash scripts/setup_ec2.sh   (実行後、いちど exit して再ログインすること)
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "==> パッケージ一覧の更新と前提ツールのインストール"
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates curl gnupg git unzip

echo "==> Docker 公式リポジトリを登録"
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
CODENAME="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")"
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "==> Docker 本体と Compose プラグインのインストール"
sudo apt-get update -qq
sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Docker を起動し、再起動後も自動起動するよう設定"
sudo systemctl enable --now docker

echo "==> $USER が sudo なしで docker を使えるようにする"
sudo usermod -aG docker "$USER"

echo "==> AWS CLI v2 のインストール (S3 アップロード用。Ubuntu には最初から入っていない)"
if ! command -v aws >/dev/null 2>&1; then
  ARCH="$(uname -m)"   # x86_64 or aarch64
  TMP="$(mktemp -d)"
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${ARCH}.zip" -o "$TMP/awscliv2.zip"
  unzip -q "$TMP/awscliv2.zip" -d "$TMP"
  sudo "$TMP/aws/install" >/dev/null
  rm -rf "$TMP"
fi

echo
echo "==> インストール結果"
docker --version
docker compose version
aws --version
echo
echo "完了しました。グループ設定を反映するため、いちど 'exit' して再ログインしてください。"
