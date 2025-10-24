import boto3
from botocore.exceptions import ClientError
import os
import logging
import uuid

logger = logging.getLogger(__name__)

# --- Reusable S3 Client (Optimization 1) ---
S3_CLIENT = None
AWS_REGION = os.getenv('AWS_DEFAULT_REGION', 'eu-north-1')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'poultry-receipts')

def get_s3_client():
    """Initializes and returns a reusable S3 client."""
    global S3_CLIENT
    if S3_CLIENT is None:
        try:
            S3_CLIENT = boto3.client('s3', region_name=AWS_REGION)
            logger.info(f"S3 client initialized for region: {AWS_REGION}")
        except Exception as e:
            logger.exception("Failed to create boto3 S3 client")
            raise
    return S3_CLIENT

# --- Pre-signed URL Generation (Optimization 3 - Best) ---

def generate_presigned_upload_url(tenant_id: str, object_id: int, filename: str, expires_in: int = 3600) -> dict:
    """
    Generates a pre-signed URL for uploading a file directly to S3.

    Args:
        tenant_id: The ID of the tenant to create a folder for.
        object_id: The ID of the object (e.g., payment_id, so_id) the receipt is for.
        filename: The original name of the file to be uploaded.
        expires_in: Time in seconds for the presigned URL to remain valid.

    Returns:
        A dictionary containing the presigned URL and the final S3 path of the object.
    """
    s3_client = get_s3_client()
    file_extension = filename.split('.')[-1] if '.' in filename else ''
    
    # Construct a unique key for the S3 object
    s3_key = f"receipts/{tenant_id}/{object_id}_{uuid.uuid4().hex}.{file_extension}"

    try:
        # Important: The client method to generate a presigned URL for uploading is 'put_object'
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expires_in
        )
        logger.info(f"Generated presigned upload URL for key: {s3_key}")
        
        # The client needs both the URL to upload to, and the final path to save in the DB
        return {"upload_url": url, "s3_path": f"s3://{S3_BUCKET_NAME}/{s3_key}"}
        
    except ClientError as e:
        logger.exception(f"Failed to generate presigned upload URL for key: {s3_key}")
        raise RuntimeError(f"Could not generate S3 upload URL: {e}")


def generate_presigned_download_url(s3_path: str, expires_in: int = 3600) -> str:
    """
    Generates a pre-signed URL for downloading a file directly from S3.

    Args:
        s3_path: The full S3 path (e.g., 's3://bucket-name/key').
        expires_in: Time in seconds for the presigned URL to remain valid.

    Returns:
        The presigned URL for downloading the object.
    """
    if not s3_path.startswith(f's3://{S3_BUCKET_NAME}/'):
        raise ValueError(f"Invalid S3 path format. Must start with 's3://{S3_BUCKET_NAME}/'")

    s3_client = get_s3_client()
    s3_key = s3_path.replace(f's3://{S3_BUCKET_NAME}/', '')

    try:
        # The client method to generate a presigned URL for downloading is 'get_object'
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expires_in
        )
        logger.info(f"Generated presigned download URL for key: {s3_key}")
        return url
        
    except ClientError as e:
        logger.exception(f"Failed to generate presigned download URL for key: {s3_key}")
        # Handle specific errors, e.g., if the object doesn't exist
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise FileNotFoundError(f"File not found in S3 at path: {s3_path}")
        raise RuntimeError(f"Could not generate S3 download URL: {e}")

