#!/usr/bin/env bash
# 講師用: 共有モードで送られた画像を置く S3 バケットを作成する
# 使い方: bash scripts/create_image_bucket.sh [バケット名] [リージョン]
#   既定: handson-chat-images / ap-northeast-1
# バケットは非公開のまま。画像は各 EC2 の API が S3 から取り出してブラウザに返すので、公開設定は不要。
set -euo pipefail

BUCKET="${1:-handson-chat-images}"
REGION="${2:-ap-northeast-1}"

if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null 2>&1; then
  echo "バケット '$BUCKET' は既に存在します。"
else
  echo "==> バケット '$BUCKET' を作成します ($REGION, 非公開)"
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  fi
fi

echo "==> パブリックアクセスをブロック (非公開のまま運用する)"
aws s3api put-public-access-block --bucket "$BUCKET" --region "$REGION" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "==> 30 日で画像を自動削除するライフサイクルを設定"
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --region "$REGION" --lifecycle-configuration '{
  "Rules": [{"ID": "expire-chat-images", "Status": "Enabled", "Filter": {"Prefix": "chat-images/"}, "Expiration": {"Days": 30}}]
}' >/dev/null

echo
echo "完了しました。"
echo "  バケット名 : $BUCKET"
echo "  リージョン : $REGION"
echo
echo "研修生の EC2 に付ける IAM ロールには docs/iam_dynamodb_policy.json の SharedChatImages の内容 (Resource をこのバケットに) を追加してください。"
echo "研修生はアプリの「設定」で、テーブル名と一緒に画像用 S3 バケット名を入力します。"
