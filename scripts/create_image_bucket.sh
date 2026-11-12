#!/usr/bin/env bash
# 講師用: 共有 DynamoDB モードで送った画像を置く S3 バケットを作成し、EC2 ロールに読み書き権限を付ける
# 使い方: bash scripts/create_image_bucket.sh [バケット名] [リージョン] [ロール名]
#   既定: handson-chat-images-<アカウントID> / ap-northeast-1 / handson-ec2-role
# バケットは非公開 (パブリックアクセスをすべてブロック)。画面には API が署名付き URL を返して表示する。
set -euo pipefail

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${1:-handson-chat-images-${ACCOUNT}}"
REGION="${2:-ap-northeast-1}"
ROLE="${3:-handson-ec2-role}"

if aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  echo "バケット '$BUCKET' は既に存在します。"
else
  echo "==> バケット '$BUCKET' を作成します ($REGION)"
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
fi

echo "==> パブリックアクセスをすべてブロック"
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "==> EC2 ロール '$ROLE' に画像の読み書き権限 (chat-images/ 配下のみ) を追加"
POLICY="$(mktemp)"
sed "s/<バケット名>/${BUCKET}/" "$(dirname "$0")/../docs/iam_s3_images_policy.json" > "$POLICY"
aws iam put-role-policy --role-name "$ROLE" --policy-name handson-chat-images --policy-document "file://$POLICY"
rm -f "$POLICY"

echo
echo "完了しました。"
echo "  バケット : $BUCKET ($REGION)"
echo "  既定と違う名前にした場合は、各 EC2 の docker-compose.yml と同じ場所の .env に"
echo "  IMAGE_BUCKET=$BUCKET を書いて docker compose up -d を実行してください。"
