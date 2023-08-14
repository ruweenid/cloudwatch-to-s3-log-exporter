# lambda_handler.py
from log_exporter import LogExporter

def lambda_handler(event, context):
    exporter = LogExporter()
    exporter.retrieve_log_groups('cluster-task')
    exporter.retrieve_log_groups('/aws/lambda')
    exporter.export_logs()
