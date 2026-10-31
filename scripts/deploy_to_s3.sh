#!/usr/bin/env bash
# web/dist を S3 バケットにアップロードし、静的ウェブサイトホスティングを有効化する
# 使い方: bash scripts/deploy_to_s3.sh <バケット名> [リージョン]
# 前提:   EC2 に S3 操作権限のある IAM ロールが付いている (または aws configure 済み)
set -euo pipefail

BUCKET="${1:-}"
REGION="${2:-ap-northeast-1}"
if [[ -z "$BUCKET" ]]; then
  echo "使い方: $0 <バケット名> [リージョン]" >&2
  exit 1
fi

DIST="$(cd "$(dirname "$0")/.." && pwd)/web/dist"
if [[ ! -f "$DIST/index.html" ]]; then
  echo "web/dist が見つかりません。先に scripts/build_for_s3.sh を実行してください。" >&2
  exit 1
fi

echo "==> バケット作成 (既にあればスキップ)"
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
fi

echo "==> パブリックアクセスブロックを解除 (研修用。業務では CloudFront + OAC を使う)"
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false

echo "==> 読み取り専用のバケットポリシーを設定"
aws s3api put-bucket-policy --bucket "$BUCKET" --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [{
    \"Sid\": \"PublicReadGetObject\",
    \"Effect\": \"Allow\",
    \"Principal\": \"*\",
    \"Action\": \"s3:GetObject\",
    \"Resource\": \"arn:aws:s3:::${BUCKET}/*\"
  }]
}"

echo "==> 静的ウェブサイトホスティングを有効化"
aws s3 website "s3://${BUCKET}" --index-document index.html --error-document index.html

echo "==> ファイルをアップロード"
aws s3 sync "$DIST" "s3://${BUCKET}" --delete

echo
echo "==> 完了。ブラウザで開いてください:"
echo "    http://${BUCKET}.s3-website-${REGION}.amazonaws.com"
