"""
S3/Tigris image storage for receipt images.
In production: Tigris object storage via AWS S3-compatible API.
In development (DEBUG=True): moto ThreadedMotoServer auto-started by apps.py.
"""

import os
import boto3
from botocore.client import Config


def _s3():
    return boto3.client(
        's3',
        endpoint_url=os.environ['AWS_ENDPOINT_URL_S3'],
        config=Config(s3={'addressing_style': 'path'}),
    )


def _bucket():
    return os.environ['BUCKET_NAME']


def _key(receipt_id):
    return f"receipts/{receipt_id}.jpg"


def store_receipt_image(receipt_id, image_file):
    if hasattr(image_file, 'seek'):
        image_file.seek(0)
    image_bytes = image_file.read() if hasattr(image_file, 'read') else bytes(image_file)
    content_type = getattr(image_file, 'content_type', 'image/jpeg') or 'image/jpeg'
    _s3().put_object(Bucket=_bucket(), Key=_key(receipt_id),
                     Body=image_bytes, ContentType=content_type)


def get_presigned_image_url(receipt_id, expiry=3600):
    """Returns a time-limited URL the browser fetches directly from S3/Tigris."""
    return _s3().generate_presigned_url(
        'get_object',
        Params={'Bucket': _bucket(), 'Key': _key(receipt_id)},
        ExpiresIn=expiry,
    )


def delete_receipt_image(receipt_id):
    _s3().delete_object(Bucket=_bucket(), Key=_key(receipt_id))
