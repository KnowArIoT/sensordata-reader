import json
import time
import os
import boto3

def upload(bucket, src_filepath):
    data = open(src_filepath, 'rb')

    dest_filename = os.path.basename(src_filepath)
    s3 = boto3.resource('s3')
    s3.Bucket(bucket).put_object(Key=dest_filename, Body=data)

