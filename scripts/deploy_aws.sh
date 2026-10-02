#!/usr/bin/env bash
set -euo pipefail

# Requirements: AWS CLI v2, configured credentials, zip/unzip utilities.
# Usage:
#   AWS_REGION=ap-south-1 PROJECT_NAME=fin-txn-analytics ./scripts/deploy_aws.sh

REGION="${AWS_REGION:-ap-south-1}"
PROJECT_NAME="${PROJECT_NAME:-fin-txn-analytics}"
STACK_NAME="${PROJECT_NAME}-foundation"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

command -v aws >/dev/null || { echo "AWS CLI is required."; exit 1; }

aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$ROOT_DIR/infrastructure/cloudformation.yaml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides ProjectName="$PROJECT_NAME"

BUCKET="$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='DataBucketName'].OutputValue" --output text)"
ROLE_ARN="$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='GlueRoleArn'].OutputValue" --output text)"

aws s3 cp "$ROOT_DIR/src/etl/glue_financial_etl.py" "s3://$BUCKET/scripts/glue_financial_etl.py" --region "$REGION"
aws s3 cp "$ROOT_DIR/data/transactions_raw.csv" "s3://$BUCKET/bronze/transactions/transactions_raw.csv" --region "$REGION"

if aws glue get-job --region "$REGION" --name "${PROJECT_NAME}-etl" >/dev/null 2>&1; then
  aws glue update-job --region "$REGION" --job-name "${PROJECT_NAME}-etl" --job-update "$(python scripts/render_glue_job_update.py "$BUCKET" "$ROLE_ARN" "$PROJECT_NAME")"
else
  aws glue create-job --region "$REGION" --cli-input-json "$(python scripts/render_glue_job_create.py "$BUCKET" "$ROLE_ARN" "$PROJECT_NAME")"
fi

echo
printf 'AWS foundation ready.\nBucket: %s\nGlue role: %s\n' "$BUCKET" "$ROLE_ARN"
echo "Start ETL with:"
echo "aws glue start-job-run --region $REGION --job-name ${PROJECT_NAME}-etl"
