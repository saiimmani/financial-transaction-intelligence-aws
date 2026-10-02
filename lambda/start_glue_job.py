"""Start the ETL job when a transaction file lands in the Bronze S3 prefix."""
from __future__ import annotations

import os
import boto3


glue = boto3.client("glue")
EXPECTED_BUCKET = os.environ["EXPECTED_BUCKET"]
EXPECTED_PREFIX = os.getenv("EXPECTED_PREFIX", "bronze/transactions/")
GLUE_JOB_NAME = os.environ["GLUE_JOB_NAME"]


def lambda_handler(event, context):
    started = []
    for record in event.get("Records", []):
        bucket = record.get("s3", {}).get("bucket", {}).get("name")
        key = record.get("s3", {}).get("object", {}).get("key", "")
        if bucket != EXPECTED_BUCKET or not key.startswith(EXPECTED_PREFIX):
            continue
        if key.endswith("/"):
            continue
        response = glue.start_job_run(
            JobName=GLUE_JOB_NAME,
            Arguments={"--TRIGGERED_OBJECT": f"s3://{bucket}/{key}"},
        )
        started.append(response["JobRunId"])
    return {"started_job_runs": started}
