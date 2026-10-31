#!/usr/bin/env bash
# S3 静的ホスティング用のファイル一式を web/dist に出力する (再ビルド不要)
#   起動中の web コンテナから配信ファイルを取り出し、API 接続先を書いた config.js を差し替える。
# 使い方: bash scripts/build_for_s3.sh http://<EC2のパブリックIP>:8000
# 出力:   web/dist/
set -euo pipefail

API_URL="${1:-}"
if [[ -z "$API_URL" ]]; then
  echo "使い方: $0 http://<EC2のパブリックIP>:8000" >&2
  exit 1
fi
API_URL="${API_URL%/}"

cd "$(dirname "$0")/.."

if ! docker compose ps --status running --services 2>/dev/null | grep -qx web; then
  echo "web コンテナが起動していません。先に 'docker compose up -d --build' を実行してください。" >&2
  exit 1
fi

rm -rf web/dist
mkdir -p web/dist
echo "==> web コンテナから配信ファイルを取り出します"
docker compose cp web:/usr/share/nginx/html/. web/dist/
rm -f web/dist/50x.html   # Nginx イメージ付属のファイルは不要

echo "==> API 接続先 $API_URL を config.js に書き込みます"
cat > web/dist/config.js <<CONF
// S3 用に生成。API の接続先を指定する (変えたい時はこのファイルだけ書き換えればよい)
window.__API_BASE_URL__ = "${API_URL}";
CONF

echo
echo "==> 出力完了: $(pwd)/web/dist"
find web/dist -type f | sort
echo
echo "次は scripts/deploy_to_s3.sh <バケット名> で S3 にアップロードします。"
echo "(画面右下の「S3 用ファイルを出力」ボタンでも同じ内容の zip が取れます)"
