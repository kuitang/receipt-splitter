#!/usr/bin/env python3
"""
Test support for different image formats (JPEG, PNG, HEIC, WebP)
"""

import os
import sys
from pathlib import Path
from io import BytesIO

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'receipt_splitter.settings')
import django
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from receipts.models import Receipt, LineItem
from PIL import Image
import pillow_heif

# Register HEIF opener
pillow_heif.register_heif_opener()


def create_test_image(format_type, size=(100, 100)):
    """Create a test image in the specified format"""
    
    # Create a simple test image with text
    img = Image.new('RGB', size, color='white')
    
    # Convert to bytes
    buffer = BytesIO()
    
    if format_type.upper() in ['HEIC', 'HEIF']:
        # For HEIC, save as JPEG first then would need conversion
        # For testing, we'll use the actual HEIC file
        return None
    else:
        img.save(buffer, format=format_type.upper())
        return buffer.getvalue()


def test_format_support(format_name, file_extension, content_type, use_real_file=None):
    """Test upload support for a specific image format"""
    
    print(f"\n{'='*50}")
    print(f"Testing {format_name} Format")
    print(f"{'='*50}")
    
    client = Client()
    
    # Clean up previous test
    Receipt.objects.filter(uploader_name=f'{format_name} Test').delete()
    
    if use_real_file:
        # Use real file for HEIC
        with open(use_real_file, 'rb') as f:
            image_data = f.read()
        print(f"Using real file: {use_real_file}")
    else:
        # Create test image
        image_data = create_test_image(format_name)
        if not image_data:
            print(f"⚠️  Cannot create synthetic {format_name} image")
            return False
        print(f"Created synthetic {format_name} image")
    
    # Create uploaded file
    uploaded_file = SimpleUploadedFile(
        name=f'test_receipt.{file_extension}',
        content=image_data,
        content_type=content_type
    )
    
    # Upload
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': f'{format_name} Test'
    })
    
    print(f"Upload Status: {response.status_code}")
    
    if response.status_code == 302:
        print(f"✅ {format_name} upload successful")
        print(f"   Redirect: {response.url}")
        
        # Check created receipt
        try:
            receipt = Receipt.objects.filter(uploader_name=f'{format_name} Test').latest('created_at')
            print(f"   Receipt created: {receipt.restaurant_name}")
            
            if use_real_file and "IMG_6839" in use_real_file:
                # Verify OCR worked for real HEIC
                if receipt.restaurant_name == "The Gin Mill (NY)":
                    print(f"   ✅ OCR extraction successful for {format_name}")
                else:
                    print(f"   ⚠️  OCR extracted: {receipt.restaurant_name}")
            
            return True
            
        except Receipt.DoesNotExist:
            print(f"   ❌ Receipt not created")
            return False
    else:
        print(f"❌ {format_name} upload failed")
        return False


def main():
    """Run image format tests"""
    
    print("\n" + "="*60)
    print("IMAGE FORMAT SUPPORT TESTS")
    print("="*60)
    
    # Check for API key
    from django.conf import settings
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_api_key_here":
        print("✅ OpenAI API key configured")
    else:
        print("⚠️  No API key - will use mock data")
    
    test_results = []
    
    # Test different formats
    formats_to_test = [
        ('JPEG', 'jpg', 'image/jpeg', None),
        ('PNG', 'png', 'image/png', None),
        ('HEIC', 'heic', 'image/heic', 'IMG_6839.HEIC'),
        ('WebP', 'webp', 'image/webp', None),
    ]
    
    for format_name, extension, content_type, real_file in formats_to_test:
        if real_file and not Path(real_file).exists():
            print(f"\n⚠️  Skipping {format_name}: {real_file} not found")
            test_results.append((format_name, False))
            continue
            
        result = test_format_support(format_name, extension, content_type, real_file)
        test_results.append((format_name, result))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for format_name, result in test_results:
        status = "✅ SUPPORTED" if result else "❌ NOT SUPPORTED"
        print(f"   {format_name:10} {status}")
    
    all_passed = all(result for _, result in test_results)
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL IMAGE FORMATS SUPPORTED")
    else:
        print("⚠️  SOME FORMATS NOT SUPPORTED")
    print("="*60)
    
    # Cleanup
    print("\nCleaning up test receipts...")
    for format_name, _, _, _ in formats_to_test:
        Receipt.objects.filter(uploader_name=f'{format_name} Test').delete()
    print("✅ Cleanup complete")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())