# Deployment scripts

- `deploy_aws.sh` — deploy S3/Glue foundation, upload the Glue scripts and Bronze data, and create/update the Glue job.
- `configure_lambda.sh` — package and deploy the Lambda Glue-job trigger.
- `render_glue_job_create.py` / `render_glue_job_update.py` — generate AWS CLI JSON for the Glue job configuration.

These scripts assume AWS CLI v2 and configured credentials.
