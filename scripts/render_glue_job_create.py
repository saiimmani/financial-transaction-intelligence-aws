import json, sys
bucket, role, project = sys.argv[1:]
print(json.dumps({
  "Name": f"{project}-etl",
  "Role": role,
  "GlueVersion": "6.0",
  "WorkerType": "G.1X",
  "NumberOfWorkers": 2,
  "Command": {
    "Name": "glueetl",
    "PythonVersion": "3",
    "ScriptLocation": f"s3://{bucket}/scripts/glue_financial_etl.py"
  },
  "DefaultArguments": {
    "--job-language": "python",
    "--enable-metrics": "true",
    "--enable-continuous-cloudwatch-log": "true",
    "--SOURCE_PATH": f"s3://{bucket}/bronze/transactions/",
    "--SILVER_PATH": f"s3://{bucket}/silver/transactions/",
    "--GOLD_PATH": f"s3://{bucket}/gold/",
    "--QUARANTINE_PATH": f"s3://{bucket}/quarantine/"
  },
  "ExecutionProperty": {"MaxConcurrentRuns": 1}
}))
