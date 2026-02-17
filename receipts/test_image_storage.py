"""
Unit tests for S3/Tigris image storage using moto @mock_aws.
Replaces test_image_memory.py coverage.
"""

import os
import uuid
import pytest
import django
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'receipt_splitter.settings')
os.environ['AWS_ACCESS_KEY_ID'] = 'test'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_REGION'] = 'us-east-1'


def _setup_moto_env():
    """Set env vars needed by image_storage._s3() and _bucket()."""
    os.environ['AWS_ENDPOINT_URL_S3'] = 'http://localhost:5566'  # overridden by mock
    os.environ['BUCKET_NAME'] = 'test-receipts'


class ImageStorageTests(TestCase):
    """Tests for store_receipt_image, get_presigned_image_url, delete_receipt_image."""

    def setUp(self):
        from moto import mock_aws
        self.mock = mock_aws()
        self.mock.start()
        _setup_moto_env()

        import boto3
        from botocore.client import Config
        s3 = boto3.client('s3', region_name='us-east-1',
                          config=Config(s3={'addressing_style': 'path'}))
        s3.create_bucket(Bucket='test-receipts')

    def tearDown(self):
        self.mock.stop()

    def test_store_receipt_image_puts_object(self):
        from receipts.image_storage import store_receipt_image
        import boto3
        from botocore.client import Config

        receipt_id = uuid.uuid4()
        image_data = b'FAKEJPEG'

        from io import BytesIO
        f = BytesIO(image_data)
        f.content_type = 'image/jpeg'
        store_receipt_image(receipt_id, f)

        s3 = boto3.client('s3', region_name='us-east-1',
                          config=Config(s3={'addressing_style': 'path'}))
        obj = s3.get_object(Bucket='test-receipts', Key=f'receipts/{receipt_id}.jpg')
        self.assertEqual(obj['Body'].read(), image_data)

    def test_get_presigned_image_url_contains_key(self):
        from receipts.image_storage import store_receipt_image, get_presigned_image_url
        from io import BytesIO

        receipt_id = uuid.uuid4()
        f = BytesIO(b'FAKEJPEG')
        f.content_type = 'image/jpeg'
        store_receipt_image(receipt_id, f)

        url = get_presigned_image_url(receipt_id)
        self.assertIn(f'receipts/{receipt_id}.jpg', url)

    def test_delete_receipt_image_removes_object(self):
        from receipts.image_storage import store_receipt_image, delete_receipt_image
        import boto3
        from botocore.client import Config
        from botocore.exceptions import ClientError
        from io import BytesIO

        receipt_id = uuid.uuid4()
        f = BytesIO(b'FAKEJPEG')
        f.content_type = 'image/jpeg'
        store_receipt_image(receipt_id, f)

        delete_receipt_image(receipt_id)

        s3 = boto3.client('s3', region_name='us-east-1',
                          config=Config(s3={'addressing_style': 'path'}))
        with self.assertRaises(ClientError):
            s3.get_object(Bucket='test-receipts', Key=f'receipts/{receipt_id}.jpg')

    def test_store_accepts_bytes_without_seek(self):
        from receipts.image_storage import store_receipt_image
        import boto3
        from botocore.client import Config

        receipt_id = uuid.uuid4()
        store_receipt_image(receipt_id, b'RAWBYTES')

        s3 = boto3.client('s3', region_name='us-east-1',
                          config=Config(s3={'addressing_style': 'path'}))
        obj = s3.get_object(Bucket='test-receipts', Key=f'receipts/{receipt_id}.jpg')
        self.assertEqual(obj['Body'].read(), b'RAWBYTES')


class ServeReceiptImageViewTests(TestCase):
    """Test that serve_receipt_image view returns HTTP 302 to a presigned URL."""

    def setUp(self):
        from moto import mock_aws
        self.mock = mock_aws()
        self.mock.start()
        _setup_moto_env()

        import boto3
        from botocore.client import Config
        s3 = boto3.client('s3', region_name='us-east-1',
                          config=Config(s3={'addressing_style': 'path'}))
        s3.create_bucket(Bucket='test-receipts')

    def tearDown(self):
        self.mock.stop()

    def test_serve_receipt_image_redirects(self):
        """serve_receipt_image returns 302 with Location containing the S3 key."""
        from django.test import RequestFactory
        from receipts.views import serve_receipt_image
        from receipts.image_storage import store_receipt_image
        from io import BytesIO
        import uuid
        from unittest.mock import MagicMock, patch

        receipt_id = uuid.uuid4()
        f = BytesIO(b'FAKEJPEG')
        f.content_type = 'image/jpeg'
        store_receipt_image(receipt_id, f)

        mock_receipt = MagicMock()
        mock_receipt.id = receipt_id
        mock_receipt.slug = 'abc123'

        mock_user_context = MagicMock()
        mock_user_context.is_uploader = True

        factory = RequestFactory()
        request = factory.get('/receipts/image/abc123/')
        request.user_context = lambda rid: mock_user_context

        with patch('receipts.views.receipt_service') as mock_service:
            mock_service.get_receipt_by_slug.return_value = mock_receipt
            response = serve_receipt_image(request, 'abc123')

        self.assertEqual(response.status_code, 302)
        self.assertIn(f'receipts/{receipt_id}.jpg', response['Location'])

    def test_serve_receipt_image_403_non_uploader(self):
        """Non-uploaders get 403."""
        from django.test import RequestFactory
        from receipts.views import serve_receipt_image
        from unittest.mock import MagicMock, patch
        import uuid

        receipt_id = uuid.uuid4()
        mock_receipt = MagicMock()
        mock_receipt.id = receipt_id
        mock_receipt.slug = 'abc123'

        mock_user_context = MagicMock()
        mock_user_context.is_uploader = False

        factory = RequestFactory()
        request = factory.get(f'/receipts/image/abc123/')
        request.user_context = lambda rid: mock_user_context

        with patch('receipts.views.receipt_service') as mock_service:
            mock_service.get_receipt_by_slug.return_value = mock_receipt
            response = serve_receipt_image(request, 'abc123')

        self.assertEqual(response.status_code, 403)
