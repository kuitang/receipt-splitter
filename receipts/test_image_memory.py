"""
Unit tests for in-memory image handling.
Verifies that no filesystem operations occur for receipt images.
"""

import io
import os
import tempfile
from unittest import mock
from django.test import TestCase, TransactionTestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from PIL import Image

from .models import Receipt, LineItem
from .image_storage import (
    store_receipt_image_in_memory,
    get_receipt_image_from_memory,
    delete_receipt_image_from_memory,
    IMAGE_CACHE_TIMEOUT
)
from .image_utils import convert_to_jpeg_if_needed, get_image_bytes_for_ocr
from .async_processor import create_placeholder_receipt


class NoFileSystemMixin:
    """Mixin to ensure no filesystem operations occur"""
    
    def setUp(self):
        super().setUp()
        # Patch file operations to detect any filesystem access
        self.file_open_patch = mock.patch('builtins.open', side_effect=AssertionError("Filesystem access detected: open()"))
        self.os_open_patch = mock.patch('os.open', side_effect=AssertionError("Filesystem access detected: os.open()"))
        self.os_write_patch = mock.patch('os.write', side_effect=AssertionError("Filesystem access detected: os.write()"))
        self.os_makedirs_patch = mock.patch('os.makedirs', side_effect=AssertionError("Filesystem access detected: os.makedirs()"))
        
        # Allow specific exceptions for Django internals
        self.original_open = open
        def filtered_open(path, *args, **kwargs):
            path_str = str(path)
            # Allow Django's internal files and our source code
            allowed_patterns = [
                '.py',  # Python source files
                'migrations',  # Django migrations
                'venv/',  # Virtual environment
                'django/',  # Django framework
                '.sqlite',  # Database
                'test_',  # Test files
                'pytest-cache',  # Pytest cache directory
                'pytest_cache',
            ]
            if any(pattern in path_str for pattern in allowed_patterns):
                return self.original_open(path, *args, **kwargs)
            raise AssertionError(f"Filesystem access detected: open({path})")
        
        self.file_open_patch = mock.patch('builtins.open', side_effect=filtered_open)
        self.file_open_patch.start()
        
    def tearDown(self):
        self.file_open_patch.stop()
        super().tearDown()


class ImageStorageTestCase(NoFileSystemMixin, TestCase):
    """Test the image_storage module"""
    
    def test_store_and_retrieve_image(self):
        """Test storing and retrieving image from memory"""
        receipt = Receipt.objects.create(
            uploader_name='Test User',
            restaurant_name='Test Restaurant',
            date=timezone.now(),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('2.00'),
            total=Decimal('13.00')
        )
        
        # Create test image data
        test_image_data = b'Test image content'
        test_file = SimpleUploadedFile(
            name='test.jpg',
            content=test_image_data,
            content_type='image/jpeg'
        )
        
        # Store image
        result = store_receipt_image_in_memory(receipt.id, test_file)
        self.assertTrue(result)
        
        # Retrieve image
        retrieved_data, content_type = get_receipt_image_from_memory(receipt.id)
        self.assertEqual(retrieved_data, test_image_data)
        self.assertEqual(content_type, 'image/jpeg')
        
    def test_delete_image_from_memory(self):
        """Test deleting image from memory"""
        receipt = Receipt.objects.create(
            uploader_name='Test User',
            restaurant_name='Test Restaurant',
            date=timezone.now(),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('2.00'),
            total=Decimal('13.00')
        )
        
        # Store image
        cache_key = f"receipt_image_{receipt.id}"
        cache.set(cache_key, b'test data', timeout=IMAGE_CACHE_TIMEOUT)
        cache.set(f"{cache_key}_type", "image/jpeg", timeout=IMAGE_CACHE_TIMEOUT)
        
        # Verify it's stored
        self.assertIsNotNone(cache.get(cache_key))
        
        # Delete image
        delete_receipt_image_from_memory(receipt.id)
        
        # Verify it's deleted
        self.assertIsNone(cache.get(cache_key))
        self.assertIsNone(cache.get(f"{cache_key}_type"))
        
    def test_image_not_found(self):
        """Test retrieving non-existent image"""
        import uuid
        fake_id = uuid.uuid4()
        retrieved_data, content_type = get_receipt_image_from_memory(fake_id)
        self.assertIsNone(retrieved_data)
        self.assertIsNone(content_type)


class ImageUtilsTestCase(NoFileSystemMixin, TestCase):
    """Test the image_utils module"""
    
    def test_jpeg_passthrough(self):
        """Test that JPEG images are not converted"""
        # Create a real JPEG image in memory
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        test_file = InMemoryUploadedFile(
            buffer,
            'ImageField',
            'test.jpg',
            'image/jpeg',
            buffer.getbuffer().nbytes,
            None
        )
        
        # Process the file
        result = convert_to_jpeg_if_needed(test_file)
        
        # Should return the same file
        self.assertEqual(result.name, 'test.jpg')
        self.assertEqual(result.content_type, 'image/jpeg')
        
    def test_png_passthrough(self):
        """Test that PNG images are not converted"""
        # Create a PNG image in memory
        img = Image.new('RGBA', (100, 100), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        test_file = InMemoryUploadedFile(
            buffer,
            'ImageField',
            'test.png',
            'image/png',
            buffer.getbuffer().nbytes,
            None
        )
        
        # Process the file
        result = convert_to_jpeg_if_needed(test_file)
        
        # Should return the same file (not converted)
        self.assertEqual(result.name, 'test.png')
        
    def test_get_image_bytes_for_ocr(self):
        """Test extracting image bytes for OCR"""
        test_data = b'Test image data'
        test_file = SimpleUploadedFile(
            name='test.jpg',
            content=test_data,
            content_type='image/jpeg'
        )
        
        image_bytes, format_hint = get_image_bytes_for_ocr(test_file)
        
        self.assertEqual(image_bytes, test_data)
        self.assertEqual(format_hint, 'JPEG')
        
    def test_format_detection(self):
        """Test format detection from filename"""
        test_cases = [
            ('test.jpg', 'JPEG'),
            ('test.jpeg', 'JPEG'),
            ('test.png', 'PNG'),
            ('test.webp', 'WEBP'),
            ('test.heic', 'HEIC'),
            ('test.heif', 'HEIC'),
            ('test.unknown', 'JPEG'),  # Default
        ]
        
        for filename, expected_format in test_cases:
            test_file = SimpleUploadedFile(
                name=filename,
                content=b'data',
                content_type='application/octet-stream'
            )
            _, format_hint = get_image_bytes_for_ocr(test_file)
            self.assertEqual(format_hint, expected_format, f"Failed for {filename}")


class AsyncProcessorTestCase(NoFileSystemMixin, TransactionTestCase):
    """Test the async_processor module"""
    
    def test_create_placeholder_receipt_no_disk_save(self):
        """Test that placeholder receipt doesn't save image to disk"""
        # Create test image
        img = Image.new('RGB', (100, 100), color='green')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        test_file = InMemoryUploadedFile(
            buffer,
            'ImageField',
            'test.jpg',
            'image/jpeg',
            buffer.getbuffer().nbytes,
            None
        )
        
        # Create placeholder receipt
        with mock.patch('receipts.async_processor.store_receipt_image_in_memory') as mock_store:
            mock_store.return_value = True
            receipt = create_placeholder_receipt('Test User', test_file)
            
            # Verify receipt was created
            self.assertIsNotNone(receipt)
            self.assertEqual(receipt.uploader_name, 'Test User')
            self.assertEqual(receipt.processing_status, 'pending')
            
            # Verify image was stored in memory, not disk
            mock_store.assert_called_once()
            
            # Verify no image field is set on the model
            self.assertFalse(hasattr(receipt, 'image') and receipt.image)


class ViewsTestCase(NoFileSystemMixin, TransactionTestCase):
    """Test views for in-memory image serving"""
    
    def setUp(self):
        super().setUp()
        self.client.session.save()  # Ensure session exists
        
    def test_serve_receipt_image_from_memory(self):
        """Test serving image from memory via view"""
        # Create receipt
        receipt = Receipt.objects.create(
            uploader_name='Test User',
            restaurant_name='Test Restaurant',
            date=timezone.now(),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('2.00'),
            total=Decimal('13.00')
        )
        
        # Store image in memory
        test_image_data = b'Test image content'
        cache_key = f"receipt_image_{receipt.id}"
        cache.set(cache_key, test_image_data, timeout=IMAGE_CACHE_TIMEOUT)
        cache.set(f"{cache_key}_type", "image/png", timeout=IMAGE_CACHE_TIMEOUT)
        
        # Set session as uploader using correct session structure
        session = self.client.session
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(receipt.id)] = {
            'is_uploader': True,
            'edit_token': 'test-token'
        }
        session.save()
        
        # Request image
        response = self.client.get(reverse('serve_receipt_image', args=[receipt.slug]))
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, test_image_data)
        self.assertEqual(response['Content-Type'], 'image/png')
        
    def test_serve_receipt_image_not_found(self):
        """Test serving non-existent image returns 404"""
        # Create receipt without image
        receipt = Receipt.objects.create(
            uploader_name='Test User',
            restaurant_name='Test Restaurant',
            date=timezone.now(),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('2.00'),
            total=Decimal('13.00')
        )
        
        # Set session as uploader using correct session structure
        session = self.client.session
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(receipt.id)] = {
            'is_uploader': True,
            'edit_token': 'test-token'
        }
        session.save()
        
        # Request image
        response = self.client.get(reverse('serve_receipt_image', args=[receipt.slug]))
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
        
    def test_serve_receipt_image_unauthorized(self):
        """Test that non-uploaders can't see unfinalied receipt images"""
        # Create receipt
        receipt = Receipt.objects.create(
            uploader_name='Test User',
            restaurant_name='Test Restaurant',
            date=timezone.now(),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('2.00'),
            total=Decimal('13.00'),
            is_finalized=False
        )
        
        # Store image in memory
        test_image_data = b'Test image content'
        cache_key = f"receipt_image_{receipt.id}"
        cache.set(cache_key, test_image_data, timeout=IMAGE_CACHE_TIMEOUT)
        
        # Request without being uploader
        response = self.client.get(reverse('serve_receipt_image', args=[receipt.slug]))
        
        # Should return 403
        self.assertEqual(response.status_code, 403)
        
    def test_serve_receipt_image_finalized_inaccessible(self):
        """Test that finalized receipt images are not accessible (regression test for image deletion)"""
        # Create finalized receipt
        receipt = Receipt.objects.create(
            uploader_name='Test User',
            restaurant_name='Test Restaurant',
            date=timezone.now(),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('2.00'),
            total=Decimal('13.00'),
            is_finalized=True
        )
        
        # Store image in memory initially (simulating pre-finalization state)
        test_image_data = b'Test image content'
        cache_key = f"receipt_image_{receipt.id}"
        cache.set(cache_key, test_image_data, timeout=IMAGE_CACHE_TIMEOUT)
        cache.set(f"{cache_key}_type", "image/jpeg", timeout=IMAGE_CACHE_TIMEOUT)
        
        # Delete image from memory (simulating finalization behavior)
        from receipts.image_storage import delete_receipt_image_from_memory
        delete_receipt_image_from_memory(str(receipt.id))
        
        # Request from uploader - should return 404 since finalized receipts don't serve images
        session = self.client.session
        session[f'receipt_{receipt.id}_uploader_id'] = 'test-uploader-id'
        session.save()
        response = self.client.get(reverse('serve_receipt_image', args=[receipt.slug]))
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'Image not available for finalized receipts', response.content)
        
        # Request from non-uploader - should return 404 since image is deleted
        session = self.client.session
        session.pop(f'receipt_{receipt.id}_uploader_id', None)
        session.save()
        response = self.client.get(reverse('serve_receipt_image', args=[receipt.slug]))
        self.assertEqual(response.status_code, 404)


class FileSystemMonitoringTestCase(TestCase):
    """Test that monitors filesystem access"""
    
    @mock.patch('os.path.exists')
    @mock.patch('os.makedirs')
    @mock.patch('builtins.open', new_callable=mock.mock_open)
    def test_no_media_directory_access(self, mock_file, mock_makedirs, mock_exists):
        """Ensure no media directory is accessed or created"""
        from .image_storage import store_receipt_image_in_memory
        
        # Create test file
        test_file = SimpleUploadedFile(
            name='test.jpg',
            content=b'test content',
            content_type='image/jpeg'
        )
        
        # Store image (should not touch filesystem)
        import uuid
        receipt_id = uuid.uuid4()
        store_receipt_image_in_memory(receipt_id, test_file)
        
        # Verify no filesystem calls for media
        mock_makedirs.assert_not_called()
        
        # Check that open wasn't called for media files
        for call in mock_file.call_args_list:
            if call and len(call) > 0:
                args = call[0]
                if args and len(args) > 0:
                    path = str(args[0])
                    self.assertNotIn('media', path.lower())
                    self.assertNotIn('receipts/', path.lower())


from django.test import override_settings

@override_settings(RATELIMIT_ENABLE=False)
@mock.patch('receipts.services.receipt_service.process_receipt_async')
class IntegrationTestCase(TransactionTestCase):
    """Integration tests for complete upload flow"""
    
    def test_complete_upload_flow_no_disk(self, mock_process_receipt):
        """Test complete upload flow without disk access"""
        # Monitor file operations
        with mock.patch('django.core.files.storage.default_storage.save') as mock_save:
            # Create test image
            img = Image.new('RGB', (200, 200), color='yellow')
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            buffer.seek(0)
            
            # Upload receipt
            response = self.client.post(reverse('upload_receipt'), {
                'uploader_name': 'Test User',
                'receipt_image': SimpleUploadedFile('test.jpg', buffer.getvalue(), content_type='image/jpeg')
            })
            
            # Should redirect to edit page
            self.assertEqual(response.status_code, 302)
            
            # Verify no disk storage was used
            mock_save.assert_not_called()
            
            # Extract receipt slug from redirect
            redirect_url = response.url
            receipt_slug = redirect_url.split('/')[-2]
            
            # Verify receipt was created
            receipt = Receipt.objects.get(slug=receipt_slug)
            self.assertEqual(receipt.uploader_name, 'Test User')
            
            # Verify image is in memory cache
            cache_key = f"receipt_image_{receipt.id}"
            cached_image = cache.get(cache_key)
            self.assertIsNotNone(cached_image)
            
    def test_no_media_directory_created(self, mock_process_receipt):
        """Test that no media directory is created during operations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Override media root to temp directory and disable async processing
            with override_settings(MEDIA_ROOT=temp_dir):
                # Patch async processing to prevent database locks
                with mock.patch('receipts.services.receipt_service.process_receipt_async'):
                    # Upload a receipt
                    img = Image.new('RGB', (100, 100))
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG')
                    buffer.seek(0)
                    
                    response = self.client.post(reverse('upload_receipt'), {
                        'uploader_name': 'Test User',
                        'receipt_image': SimpleUploadedFile('test.jpg', buffer.getvalue())
                    })
                    
                    # Check that no subdirectories were created in media root
                    subdirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
                    self.assertEqual(len(subdirs), 0, f"Unexpected directories created: {subdirs}")
                    
                    # Check that no files were created
                    files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
                    self.assertEqual(len(files), 0, f"Unexpected files created: {files}")