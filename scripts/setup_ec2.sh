#!/usr/bin/env bash
# Amazon Linux 2023 に Docker と Docker Compose プラグインを入れるスクリプト
# 使い方: bash scripts/setup_ec2.sh   (実行後、いちど exit して再ログインすること)
set -euo pipefail

echo "==> パッケージ更新と Docker / git のインストール"
sudo dnf update -y -q
sudo dnf install -y -q docker git

echo "==> Docker を起動し、再起動後も自動起動するよう設定"
sudo systemctl enable --now docker

echo "==> ec2-user が sudo なしで docker を使えるようにする"
sudo usermod -aG docker "$USER"

echo "==> Docker Compose プラグインのインストール"
ARCH="$(uname -m)"               # x86_64 or aarch64
VERSION="$(curl -fsSL https://api.github.com/repos/docker/compose/releases/latest \
           | grep -oE '"tag_name": *"[^"]+"' | cut -d'"' -f4 || true)"
VERSION="${VERSION:-v2.29.7}"    # API が引けなかった時の予備
PLUGIN_DIR=/usr/local/lib/docker/cli-plugins
sudo mkdir -p "$PLUGIN_DIR"
sudo curl -fsSL "https://github.com/docker/compose/releases/download/${VERSION}/docker-compose-linux-${ARCH}" \
     -o "$PLUGIN_DIR/docker-compose"
sudo chmod +x "$PLUGIN_DIR/docker-compose"

echo
echo "==> インストール結果"
docker --version
docker compose version
echo
echo "完了しました。グループ設定を反映するため、いちど 'exit' して再ログインしてください。"
