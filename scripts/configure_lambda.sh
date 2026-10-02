#!/usr/bin/env bash
set -euo pipefail

# Creates the Lambda function package and wires an S3 notification.
# This script assumes the Glue role foundation is already deployed.
# It deliberately does not modify bucket notification configuration automatically;
# use EventBridge or the S3 console after creating the Lambda function to avoid circular
# CloudFormation dependencies.

REGION="${AWS_REGION:-ap-south-1}"
FUNCTION_NAME="${FUNCTION_NAME:-fin-txn-start-glue}"
GLUE_JOB_NAME="${GLUE_JOB_NAME:-fin-txn-analytics-etl}"
ROLE_ARN="${LAMBDA_ROLE_ARN:?Set LAMBDA_ROLE_ARN to a Lambda execution role ARN}"
BUCKET="${DATA_BUCKET:?Set DATA_BUCKET to the project S3 bucket}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
cp "$ROOT_DIR/lambda/start_glue_job.py" "$TMP_DIR/lambda_function.py"
(cd "$TMP_DIR" && zip -q function.zip lambda_function.py)

aws lambda create-function \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --runtime python3.13 \
  --handler lambda_function.lambda_handler \
  --role "$ROLE_ARN" \
  --zip-file "fileb://$TMP_DIR/function.zip" \
  --environment "Variables={EXPECTED_BUCKET=$BUCKET,EXPECTED_PREFIX=bronze/transactions/,GLUE_JOB_NAME=$GLUE_JOB_NAME}" || \
aws lambda update-function-code \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --zip-file "fileb://$TMP_DIR/function.zip"

echo "Lambda deployed: $FUNCTION_NAME"
echo "Configure an S3 Object Created -> Lambda EventBridge/S3 notification for prefix bronze/transactions/."
