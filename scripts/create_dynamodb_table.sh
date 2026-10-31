#!/usr/bin/env bash
# 講師用: 研修生全員で共有するチャット用 DynamoDB テーブルを作成する
# 使い方: bash scripts/create_dynamodb_table.sh [テーブル名] [リージョン]
#   既定: handson-chat / ap-northeast-1
# キー構成はアプリが前提としている pk (文字列, パーティションキー) / sk (文字列, ソートキー) 固定。
set -euo pipefail

TABLE="${1:-handson-chat}"
REGION="${2:-ap-northeast-1}"

if aws dynamodb describe-table --table-name "$TABLE" --region "$REGION" >/dev/null 2>&1; then
  echo "テーブル '$TABLE' は既に存在します ($REGION)。"
else
  echo "==> テーブル '$TABLE' を作成します ($REGION, オンデマンド課金)"
  aws dynamodb create-table \
    --table-name "$TABLE" \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region "$REGION" >/dev/null
  echo "==> 作成完了を待っています..."
  aws dynamodb wait table-exists --table-name "$TABLE" --region "$REGION"
fi

echo "==> セッションの自動削除 (TTL: expires_at) を有効化"
aws dynamodb update-time-to-live --table-name "$TABLE" --region "$REGION" \
  --time-to-live-specification "Enabled=true, AttributeName=expires_at" >/dev/null 2>&1 || true

ARN=$(aws dynamodb describe-table --table-name "$TABLE" --region "$REGION" --query 'Table.TableArn' --output text)
echo
echo "完了しました。"
echo "  テーブル名 : $TABLE"
echo "  リージョン : $REGION"
echo "  ARN        : $ARN"
echo
echo "研修生の EC2 に付ける IAM ロールには docs/iam_dynamodb_policy.json の内容 (Resource を上の ARN に) を追加してください。"
echo "研修生はアプリの「⚙️ 設定」でテーブル名とリージョンを入力して切り替えます。"
