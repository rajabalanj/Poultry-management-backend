import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
import uuid
import os
import logging
import time

logger = logging.getLogger(__name__)


def _has_aws_credentials() -> bool:
    # Checks common env vars used by boto3
    return any(os.getenv(k) for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"))


def upload_receipt_to_s3(file_content: bytes, filename: str, payment_id: int, max_retries: int = 3, backoff_base: float = 0.5) -> str:
    """Upload receipt file to S3 and return the file URL.

    Retries on transient errors with exponential backoff. Raises exceptions with context on permanent failures.
    """
    bucket_name = os.getenv('S3_BUCKET_NAME', 'poultry-receipts')
    aws_region = os.getenv('AWS_DEFAULT_REGION', 'eu-north-1')

    # Log credential presence (do not log secrets)
    logger.info(f"AWS credentials present: {_has_aws_credentials()}")
    logger.info(f"Using S3 bucket: {bucket_name} in region: {aws_region}")
    logger.info(f"File size: {len(file_content)} bytes, filename: {filename}")

    # Generate unique key
    file_extension = filename.split('.')[-1]
    s3_key = f"receipts/{payment_id}_{uuid.uuid4().hex}.{file_extension}"

    # Create client once
    try:
        s3_client = boto3.client('s3', region_name=aws_region)
        logger.info(f"S3 client created successfully for region: {aws_region}")
    except Exception as e:
        logger.exception(f"Failed to create boto3 S3 client: {e}")
        raise

    # Test bucket access before attempting upload
    try:
        logger.info(f"Testing bucket access for: {bucket_name}")
        s3_client.head_bucket(Bucket=bucket_name)
        logger.info(f"Bucket {bucket_name} is accessible")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '403':
            logger.error(f"Access denied to bucket {bucket_name}. Check IAM permissions.")
            raise RuntimeError(f"S3 bucket access denied. Check IAM user permissions for bucket: {bucket_name}")
        elif error_code == '404':
            logger.error(f"Bucket {bucket_name} not found. Check bucket name and region.")
            raise RuntimeError(f"S3 bucket not found: {bucket_name}. Check bucket name and region.")
        else:
            logger.error(f"Cannot access bucket {bucket_name}: {error_code} - {e.response['Error']['Message']}")
            raise RuntimeError(f"S3 bucket access error: {e.response['Error']['Message']}")
    except Exception as e:
        logger.error(f"Unexpected error accessing bucket {bucket_name}: {e}")
        raise RuntimeError(f"Unexpected S3 error: {str(e)}")

    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempt {attempt} to upload payment_id={payment_id} to s3://{bucket_name}/{s3_key}")
            response = s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType='application/pdf' if file_extension == 'pdf' else f'image/{file_extension}'
            )
            logger.info(f"Upload successful for payment_id={payment_id} on attempt {attempt}. Response: {response.get('ETag', 'No ETag')}")
            return f"s3://{bucket_name}/{s3_key}"
        except (EndpointConnectionError, ClientError) as e:
            last_exc = e
            # For certain ClientError codes, we may want to fail fast
            code = getattr(e, 'response', {}).get('Error', {}).get('Code') if isinstance(e, ClientError) else None
            error_msg = getattr(e, 'response', {}).get('Error', {}).get('Message', str(e)) if isinstance(e, ClientError) else str(e)
            logger.warning(f"S3 upload attempt {attempt} failed for payment_id={payment_id}, error={error_msg}, code={code}")
            
            # If it's a 4xx that indicates permission or bad request, don't retry
            if isinstance(e, ClientError) and code:
                if code in ['403', 'AccessDenied']:
                    logger.error(f"Access denied for payment_id={payment_id}. Check IAM permissions.")
                    raise RuntimeError(f"S3 access denied. Check IAM user permissions for bucket: {bucket_name}")
                elif code in ['404', 'NoSuchBucket']:
                    logger.error(f"Bucket not found for payment_id={payment_id}. Check bucket name and region.")
                    raise RuntimeError(f"S3 bucket not found: {bucket_name}. Check bucket name and region.")
                elif str(code).startswith('4'):
                    logger.error(f"Non-retriable ClientError code={code} for payment_id={payment_id}")
                    break
            
            if attempt < max_retries:
                sleep_time = backoff_base * (2 ** (attempt - 1))
                logger.debug(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                logger.error(f"All {max_retries} attempts failed for payment_id={payment_id}")
        except NoCredentialsError as e:
            logger.exception("No AWS credentials found for S3 upload")
            raise
        except Exception as e:
            last_exc = e
            logger.exception(f"Unexpected error while uploading to S3 for payment_id={payment_id}: {e}")
            # Let the retry loop continue for unexpected errors
            if attempt < max_retries:
                sleep_time = backoff_base * (2 ** (attempt - 1))
                logger.debug(f"Retrying after unexpected error in {sleep_time} seconds...")
                time.sleep(sleep_time)

    # If we get here, all retries failed
    if last_exc:
        # Provide more helpful error messages
        if isinstance(last_exc, ClientError):
            error_code = last_exc.response['Error']['Code']
            error_msg = last_exc.response['Error']['Message']
            logger.error(f"S3 upload failed permanently for payment_id={payment_id}: {error_code} - {error_msg}")
            raise RuntimeError(f"S3 upload failed: {error_msg}")
        else:
            logger.error(f"S3 upload failed permanently for payment_id={payment_id}: {last_exc}")
            raise RuntimeError(f"S3 upload failed: {str(last_exc)}")
    else:
        raise RuntimeError("Unknown failure during S3 upload")