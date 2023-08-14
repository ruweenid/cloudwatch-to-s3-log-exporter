import boto3
import datetime
import re
import concurrent.futures
import os

class LogExporter:
    def __init__(self):
        self.cloudwatch_logs = boto3.client('logs')
        self.s3 = boto3.client('s3')
        self.log_groups = []
        self.s3_bucket = os.environ.get('S3_BUCKET_NAME')
        self.max_workers = int(os.environ.get('MAX_WORKERS'))

    def retrieve_log_groups(self, pattern):
        next_token = None
        while True:
            params = {'logGroupNamePattern': pattern}
            if next_token:
                params['nextToken'] = next_token
            
            response = self.cloudwatch_logs.describe_log_groups(**params)
            self.log_groups.extend([group['logGroupName'] for group in response['logGroups']])
            
            if 'nextToken' in response:
                next_token = response['nextToken']
            else:
                break

    def process_log_group(self, log_group):
        log_streams = self.cloudwatch_logs.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True
        )['logStreams']

        for log_stream in log_streams:
            log_stream_name = log_stream['logStreamName']
            clean_log_stream_name = self.clean_for_filename(log_stream_name)

            end_time = datetime.datetime.now()
            start_time = end_time - datetime.timedelta(days=1)

            response = self.cloudwatch_logs.get_log_events(
                logGroupName=log_group,
                logStreamName=log_stream_name,
                startTime=int(start_time.timestamp()) * 1000,
                endTime=int(end_time.timestamp()) * 1000
            )

            log_events = response['events']

            if log_events:
                log_group_folder = self.clean_for_filename(log_group)
                start_date_folder = start_time.strftime('%Y-%m-%d')
                log_file_name = f"{clean_log_stream_name}-{start_time.strftime('%Y-%m-%d-%H-%M-%S')}.log"
                log_file_path = f"/tmp/{log_file_name}"

                with open(log_file_path, 'w') as log_file:
                    for event in log_events:
                        log_file.write(event['message'] + '\n')

                self.upload_to_s3(log_file_path, log_group_folder, start_date_folder, log_file_name)

    @staticmethod
    def clean_for_filename(text):
        return re.sub(r'[\/:*?"<>|]', '_', text)

    def upload_to_s3(self, file_path, log_group_folder, start_date_folder, file_name):
        self.s3.upload_file(
            file_path,
            self.s3_bucket,
            f"{log_group_folder}/{start_date_folder}/{file_name}"
        )
    
    def cleanup_temp_files(self):
        for root, dirs, files in os.walk('/tmp'):
            for file in files:
                os.remove(os.path.join(root, file))

    def export_logs(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(self.process_log_group, self.log_groups)
        self.cleanup_temp_files()
