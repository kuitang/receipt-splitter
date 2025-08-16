#!/usr/bin/env python3
"""
Test HEIC to JPEG conversion functionality
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
from receipts.models import Receipt
from receipts.image_utils import convert_to_jpeg_if_needed, get_image_bytes_for_ocr
from PIL import Image


def test_heic_conversion():
    """Test that HEIC files are converted to JPEG for storage"""
    
    print("=" * 70)
    print("HEIC TO JPEG CONVERSION TEST")
    print("=" * 70)
    
    # Load the actual HEIC test image
    heic_path = Path(__file__).parent.parent / 'IMG_6839.HEIC'
    
    if not heic_path.exists():
        print(f"\n❌ Test image not found: {heic_path}")
        return False
    
    print(f"\n✅ Found test HEIC image: {heic_path}")
    
    # Read the HEIC file
    with open(heic_path, 'rb') as f:
        heic_data = f.read()
    
    # Create a mock uploaded file
    uploaded_file = SimpleUploadedFile(
        name='test_receipt.heic',
        content=heic_data,
        content_type='image/heic'
    )
    
    print("\n1️⃣  Testing HEIC to JPEG conversion...")
    
    try:
        # Convert HEIC to JPEG
        converted_file = convert_to_jpeg_if_needed(uploaded_file)
        
        # Check the conversion
        if converted_file.name.endswith('.jpg'):
            print(f"   ✅ HEIC converted to JPEG: {converted_file.name}")
        else:
            print(f"   ❌ Conversion failed, name: {converted_file.name}")
            return False
        
        # Verify it's actually a JPEG
        converted_file.seek(0)
        img = Image.open(converted_file)
        if img.format == 'JPEG':
            print(f"   ✅ Converted file is valid JPEG format")
        else:
            print(f"   ❌ Converted file is {img.format}, not JPEG")
            return False
        
        print(f"   ✅ Image dimensions: {img.size}")
        
    except Exception as e:
        print(f"   ❌ Conversion error: {str(e)}")
        return False
    
    print("\n2️⃣  Testing non-HEIC files (should not convert)...")
    
    # Test with JPEG (should not convert)
    jpeg_data = BytesIO()
    test_img = Image.new('RGB', (100, 100), color='red')
    test_img.save(jpeg_data, format='JPEG')
    
    jpeg_file = SimpleUploadedFile(
        name='test.jpg',
        content=jpeg_data.getvalue(),
        content_type='image/jpeg'
    )
    
    not_converted = convert_to_jpeg_if_needed(jpeg_file)
    if not_converted.name == 'test.jpg':
        print(f"   ✅ JPEG file not converted: {not_converted.name}")
    else:
        print(f"   ❌ JPEG file incorrectly converted: {not_converted.name}")
        return False
    
    print("\n3️⃣  Testing OCR bytes extraction...")
    
    # Reset the HEIC file
    uploaded_file.seek(0)
    
    # Get bytes for OCR (should preserve original HEIC)
    ocr_bytes, format_hint = get_image_bytes_for_ocr(uploaded_file)
    
    if format_hint == 'HEIC':
        print(f"   ✅ Format hint correctly identified as HEIC")
    else:
        print(f"   ❌ Format hint wrong: {format_hint}")
        return False
    
    if len(ocr_bytes) == len(heic_data):
        print(f"   ✅ Original HEIC bytes preserved for OCR ({len(ocr_bytes):,} bytes)")
    else:
        print(f"   ❌ OCR bytes size mismatch")
        return False
    
    return True


def test_upload_with_conversion():
    """Test the full upload flow with HEIC conversion"""
    
    print("\n" + "=" * 70)
    print("UPLOAD WITH HEIC CONVERSION TEST")
    print("=" * 70)
    
    client = Client()
    
    # Clean up previous test receipts
    Receipt.objects.filter(uploader_name='HEIC Conversion Test').delete()
    
    # Load the HEIC image
    heic_path = Path(__file__).parent.parent / 'IMG_6839.HEIC'
    
    if not heic_path.exists():
        print(f"\n❌ Test image not found: {heic_path}")
        return False
    
    with open(heic_path, 'rb') as f:
        heic_data = f.read()
    
    uploaded_file = SimpleUploadedFile(
        name='receipt.heic',
        content=heic_data,
        content_type='image/heic'
    )
    
    print("\n1️⃣  Uploading HEIC receipt...")
    
    # Upload receipt
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'HEIC Conversion Test'
    })
    
    if response.status_code != 302:
        print(f"   ❌ Upload failed with status {response.status_code}")
        return False
    
    print(f"   ✅ Upload successful, redirected to: {response.url}")
    
    # Get the created receipt
    receipt = Receipt.objects.filter(uploader_name='HEIC Conversion Test').first()
    
    if not receipt:
        print("   ❌ Receipt not created")
        return False
    
    print(f"   ✅ Receipt created with ID: {receipt.id}")
    
    # Check the stored image
    if receipt.image:
        image_name = receipt.image.name
        if '.jpg' in image_name or '.jpeg' in image_name:
            print(f"   ✅ Stored image is JPEG: {image_name}")
        else:
            print(f"   ❌ Stored image is not JPEG: {image_name}")
            return False
    else:
        print("   ❌ No image stored")
        return False
    
    # Verify the image can be opened
    try:
        img = Image.open(receipt.image)
        print(f"   ✅ Stored image can be opened, format: {img.format}, size: {img.size}")
    except Exception as e:
        print(f"   ❌ Cannot open stored image: {str(e)}")
        return False
    
    # Clean up
    receipt.delete()
    
    return True


if __name__ == '__main__':
    print("\n🧪 RUNNING HEIC CONVERSION TESTS")
    print("=" * 70)
    
    test_results = []
    
    # Test 1: Basic conversion
    print("\n📝 Test 1: HEIC to JPEG Conversion")
    result = test_heic_conversion()
    test_results.append(("HEIC Conversion", result))
    
    # Test 2: Upload flow
    print("\n📝 Test 2: Upload with Conversion")
    result = test_upload_with_conversion()
    test_results.append(("Upload Flow", result))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    all_passed = all(result for _, result in test_results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL HEIC CONVERSION TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 70)
    
    sys.exit(0 if all_passed else 1)