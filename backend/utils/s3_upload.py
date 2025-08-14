import boto3
from botocore.exceptions import ClientError
import uuid
import os

def upload_receipt_to_s3(file_content: bytes, filename: str, po_id: int) -> str:
    """Upload receipt file to S3 and return the file URL."""
    s3_client = boto3.client('s3')
    bucket_name = os.getenv('S3_BUCKET_NAME', 'poultry-receipts')
    
    # Generate unique key
    file_extension = filename.split('.')[-1]
    s3_key = f"receipts/{po_id}_{uuid.uuid4().hex}.{file_extension}"
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf' if file_extension == 'pdf' else f'image/{file_extension}'
        )
        return f"s3://{bucket_name}/{s3_key}"
    except ClientError:
        raise Exception("Failed to upload to S3")