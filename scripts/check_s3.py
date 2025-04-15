#!/usr/bin/env python3
import os

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get AWS credentials from environment variables
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION")
s3_bucket_name = os.getenv("S3_BUCKET_NAME")

# File path from previous database query
file_key = "attachments/4/b0a420fa_test.txt"

# Create S3 client
s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region,
)

try:
    # Try to get the object to check if it exists
    response = s3.head_object(Bucket=s3_bucket_name, Key=file_key)
    print("✅ File exists in S3!")
    print(f"   Bucket: {s3_bucket_name}")
    print(f"   Key: {file_key}")
    print(f"   Size: {response['ContentLength']} bytes")
    print(f"   Last Modified: {response['LastModified']}")

    # Download the file content to verify it
    response = s3.get_object(Bucket=s3_bucket_name, Key=file_key)
    file_content = response["Body"].read().decode("utf-8")
    print("\nFile Content Preview:")
    print("-----------------")
    print(file_content)
    print("-----------------")

except ClientError as e:
    if e.response["Error"]["Code"] == "404":
        print(f"❌ The file {file_key} does not exist in bucket {s3_bucket_name}")
    else:
        print(f"❌ Error checking S3: {e}")
