"""
Strict test to ensure absolutely no filesystem operations for images.
This test uses aggressive mocking to catch any file system access.
"""

import io
import sys
from unittest import mock
from django.test import TestCase, TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image


class StrictNoFileSystemTestCase(TransactionTestCase):
    """
    Extremely strict test that fails on ANY filesystem operation
    related to image handling.
    """
    
    def test_upload_with_strict_no_filesystem(self):
        """Test upload with strict filesystem monitoring"""
        
        # Create a list to track any file operations
        file_operations = []
        
        # Create test image
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        original_open = open
        original_os_open = os.open if hasattr(os, 'open') else None
        
        def monitor_open(path, *args, **kwargs):
            """Monitor and record file open operations"""
            path_str = str(path)
            
            # List of allowed paths (Django internals, Python libs, etc.)
            allowed = [
                '.py',  # Python source
                'site-packages',  # Installed packages
                '__pycache__',  # Python cache
                '.sqlite',  # Database
                'migrations',  # Django migrations
                '/usr/',  # System libraries
                '/lib/',  # System libraries
                sys.prefix,  # Python installation
            ]
            
            # Check if this is an allowed path
            is_allowed = any(allow in path_str for allow in allowed)
            
            # Record suspicious paths
            if not is_allowed and 'media' in path_str.lower():
                file_operations.append(('open', path_str))
                raise AssertionError(f"Detected media file access: {path_str}")
            
            if not is_allowed and 'receipt' in path_str.lower() and not path_str.endswith('.py'):
                file_operations.append(('open', path_str))
                raise AssertionError(f"Detected receipt file access: {path_str}")
                
            return original_open(path, *args, **kwargs)
        
        def monitor_os_open(path, *args, **kwargs):
            """Monitor os.open operations"""
            path_str = str(path)
            if 'media' in path_str.lower() or ('receipt' in path_str.lower() and not path_str.endswith('.py')):
                file_operations.append(('os.open', path_str))
                raise AssertionError(f"Detected OS file access: {path_str}")
            return original_os_open(path, *args, **kwargs) if original_os_open else None
        
        # Patch file operations
        with mock.patch('builtins.open', side_effect=monitor_open):
            with mock.patch('os.open', side_effect=monitor_os_open) if original_os_open else mock.patch('os.path.exists'):
                with mock.patch('os.makedirs') as mock_makedirs:
                    with mock.patch('os.path.isdir', return_value=False):
                        # Attempt upload
                        response = self.client.post(reverse('upload_receipt'), {
                            'uploader_name': 'Test User',
                            'receipt_image': SimpleUploadedFile(
                                'test.jpg', 
                                buffer.getvalue(), 
                                content_type='image/jpeg'
                            )
                        })
                        
                        # Should succeed without filesystem access
                        self.assertEqual(response.status_code, 302)
                        
                        # Verify no media directories were created
                        mock_makedirs.assert_not_called()
                        
                        # Verify no suspicious file operations
                        self.assertEqual(
                            len(file_operations), 0,
                            f"Detected file operations: {file_operations}"
                        )
    
    def test_image_serving_no_filesystem(self):
        """Test image serving without filesystem access"""
        from receipts.models import Receipt
        from django.utils import timezone
        from decimal import Decimal
        from django.core.cache import cache
        
        # Create receipt
        receipt = Receipt.objects.create(
            uploader_name='Test User',
            restaurant_name='Test Restaurant',
            date=timezone.now(),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('2.00'),
            total=Decimal('13.00'),
            is_finalized=True  # Make it public
        )
        
        # Store image in cache
        test_image = b'Test image data'
        cache.set(f'receipt_image_{receipt.id}', test_image, timeout=3600)
        cache.set(f'receipt_image_{receipt.id}_type', 'image/jpeg', timeout=3600)
        
        # Monitor filesystem
        file_operations = []
        original_open = open
        
        def monitor_open(path, *args, **kwargs):
            path_str = str(path)
            if 'media' in path_str.lower():
                file_operations.append(path_str)
                raise AssertionError(f"Attempted to access media: {path_str}")
            if 'receipt' in path_str.lower() and not path_str.endswith('.py'):
                file_operations.append(path_str)
                raise AssertionError(f"Attempted to access receipt file: {path_str}")
            return original_open(path, *args, **kwargs)
        
        with mock.patch('builtins.open', side_effect=monitor_open):
            # Request image
            response = self.client.get(
                reverse('serve_receipt_image', args=[receipt.slug])
            )
            
            # Should succeed
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, test_image)
            
            # No filesystem access
            self.assertEqual(len(file_operations), 0)


import os
class FileSystemAssertions:
    """Helper class for filesystem assertions"""
    
    @staticmethod
    def assert_no_media_access(test_func):
        """Decorator to ensure no media access during test"""
        def wrapper(self):
            original_open = open
            accessed_paths = []
            
            def tracking_open(path, *args, **kwargs):
                path_str = str(path).lower()
                if 'media' in path_str or 'upload' in path_str:
                    accessed_paths.append(path_str)
                return original_open(path, *args, **kwargs)
            
            with mock.patch('builtins.open', side_effect=tracking_open):
                result = test_func(self)
                
                # Check for media access
                media_paths = [p for p in accessed_paths if 'media' in p]
                if media_paths:
                    raise AssertionError(f"Media paths accessed: {media_paths}")
                
                return result
        
        return wrapper