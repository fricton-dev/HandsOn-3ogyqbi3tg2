#!/usr/bin/env bash
# 講師用: 共有モードで送られた画像を置く S3 バケットを作成し、EC2 ロールに読み書き権限を付ける
# 使い方: bash scripts/create_image_bucket.sh [バケット名] [リージョン] [ロール名]
#   既定: handson-chat-images-<アカウントID> / ap-northeast-1 / handson-ec2-role
# バケットは非公開のまま。画像は各 EC2 の API が S3 から取り出してブラウザに返すので、公開設定は不要。
set -euo pipefail

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${1:-handson-chat-images-${ACCOUNT}}"
REGION="${2:-ap-northeast-1}"
ROLE="${3:-handson-ec2-role}"

if aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
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

echo "==> パブリックアクセスをすべてブロック (非公開のまま運用する)"
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "==> 30 日で画像を自動削除するライフサイクルを設定"
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --lifecycle-configuration '{
  "Rules": [{"ID": "expire-chat-images", "Status": "Enabled", "Filter": {"Prefix": "chat-images/"}, "Expiration": {"Days": 30}}]
}' >/dev/null

if aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  echo "==> EC2 ロール '$ROLE' に chat-images/ 配下の読み書き権限を追加"
  POLICY="$(mktemp)"
  sed "s/<バケット名>/${BUCKET}/" "$(dirname "$0")/../docs/iam_s3_images_policy.json" > "$POLICY"
  aws iam put-role-policy --role-name "$ROLE" --policy-name handson-chat-images --policy-document "file://$POLICY"
  rm -f "$POLICY"
else
  echo "==> ロール '$ROLE' が無いため権限の付与は省略しました。docs/iam_s3_images_policy.json の内容を EC2 ロールに追加してください。"
fi

echo
echo "完了しました。"
echo "  バケット名 : $BUCKET"
echo "  リージョン : $REGION"
echo
echo "docker-compose.yml の IMAGE_BUCKET の既定値と同じ名前なら、研修生側の設定画面に最初から入ります。"
echo "別の名前にした場合は、研修生に設定画面の「画像用 S3 バケット」へ入力してもらうか、.env に IMAGE_BUCKET=$BUCKET を書いてもらってください。"
