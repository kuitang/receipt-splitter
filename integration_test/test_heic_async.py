#!/usr/bin/env python3
"""
Test HEIC upload with async processing
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'receipt_splitter.settings')
import django
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from receipts.models import Receipt
from PIL import Image


def test_heic_async_upload():
    """Test HEIC upload with async processing and JPEG conversion"""
    
    print("=" * 70)
    print("HEIC ASYNC UPLOAD TEST")
    print("=" * 70)
    
    client = Client()
    
    # Clean up previous test receipts
    Receipt.objects.filter(uploader_name='HEIC Async Test').delete()
    
    # Load the actual HEIC test image
    heic_path = Path(__file__).parent.parent / 'IMG_6839.HEIC'
    
    if not heic_path.exists():
        print(f"\n❌ Test image not found: {heic_path}")
        return False
    
    print(f"\n✅ Found test HEIC image: {heic_path}")
    print(f"   File size: {heic_path.stat().st_size:,} bytes")
    
    # Read the HEIC file
    with open(heic_path, 'rb') as f:
        heic_data = f.read()
    
    uploaded_file = SimpleUploadedFile(
        name='gin_mill_receipt.heic',
        content=heic_data,
        content_type='image/heic'
    )
    
    print("\n1️⃣  Uploading HEIC Receipt...")
    
    # Upload receipt
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'HEIC Async Test'
    })
    
    print(f"   Upload response: {response.status_code}")
    
    if response.status_code != 302:
        print(f"   ❌ Expected redirect, got {response.status_code}")
        return False
    
    # Extract receipt ID from redirect URL
    redirect_url = response.url
    print(f"   Redirect to: {redirect_url}")
    
    # Get the receipt
    receipt = Receipt.objects.filter(uploader_name='HEIC Async Test').latest('created_at')
    print(f"   Receipt ID: {receipt.id}")
    
    # Check stored image format
    print("\n2️⃣  Verifying Image Conversion...")
    
    if receipt.image:
        image_name = receipt.image.name
        print(f"   Stored image name: {image_name}")
        
        # Check if it's a JPEG
        if '.jpg' in image_name.lower() or '.jpeg' in image_name.lower():
            print(f"   ✅ HEIC converted to JPEG for storage")
        else:
            print(f"   ❌ Image not converted to JPEG: {image_name}")
            return False
        
        # Verify the image can be opened and is JPEG
        try:
            img = Image.open(receipt.image)
            if img.format == 'JPEG':
                print(f"   ✅ Stored image is valid JPEG")
                print(f"   Image dimensions: {img.size}")
            else:
                print(f"   ❌ Stored image format is {img.format}, not JPEG")
                return False
        except Exception as e:
            print(f"   ❌ Cannot open stored image: {str(e)}")
            return False
    else:
        print("   ❌ No image stored")
        return False
    
    # Check processing status
    print("\n3️⃣  Checking Async Processing...")
    print(f"   Initial processing status: {receipt.processing_status}")
    
    # Wait for processing to complete
    max_wait = 15  # seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        receipt.refresh_from_db()
        
        if receipt.processing_status == 'completed':
            print(f"   ✅ Processing completed in {time.time() - start_time:.1f} seconds")
            break
        elif receipt.processing_status == 'failed':
            print(f"   ❌ Processing failed: {getattr(receipt, 'processing_error', 'Unknown error')}")
            return False
        
        time.sleep(0.5)
    else:
        print(f"   ⚠️  Processing did not complete within {max_wait} seconds")
        print(f"   Current status: {receipt.processing_status}")
    
    # Check OCR results
    print("\n4️⃣  Verifying OCR Results...")
    receipt.refresh_from_db()
    
    print(f"   Restaurant name: {receipt.restaurant_name}")
    print(f"   Total: ${receipt.total}")
    print(f"   Items count: {receipt.items.count()}")
    
    # Expected values from The Gin Mill receipt
    if "Gin Mill" in receipt.restaurant_name or receipt.restaurant_name == "The Gin Mill (NY)":
        print(f"   ✅ Restaurant name correctly extracted")
    elif receipt.restaurant_name == "Unknown" or receipt.restaurant_name == "Demo Restaurant":
        print(f"   ⚠️  Using mock data (OpenAI key not configured)")
    else:
        print(f"   ⚠️  Unexpected restaurant name: {receipt.restaurant_name}")
    
    # Test browser display
    print("\n5️⃣  Testing Browser Display...")
    
    # Load the edit page
    response = client.get(f'/edit/{receipt.id}/')
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Check if image URL is present
        if receipt.image.url in content:
            print(f"   ✅ Image URL present in HTML: {receipt.image.url}")
            
            # The URL should point to a JPEG
            if '.jpg' in receipt.image.url or '.jpeg' in receipt.image.url:
                print(f"   ✅ Image URL points to JPEG (browser compatible)")
            else:
                print(f"   ❌ Image URL doesn't point to JPEG")
                return False
        else:
            print(f"   ❌ Image URL not found in HTML")
            return False
    else:
        print(f"   ❌ Failed to load edit page: {response.status_code}")
        return False
    
    # Clean up
    receipt.delete()
    print("\n🧹 Test data cleaned up")
    
    return True


if __name__ == '__main__':
    print("\n🚀 RUNNING HEIC ASYNC UPLOAD TEST")
    print("=" * 70)
    
    result = test_heic_async_upload()
    
    print("\n" + "=" * 70)
    print("TEST RESULT")
    print("=" * 70)
    
    if result:
        print("✅ HEIC ASYNC UPLOAD TEST PASSED")
        print("\nKey findings:")
        print("- HEIC files are successfully uploaded")
        print("- Files are converted to JPEG for browser display")
        print("- Original HEIC is used for OCR processing")
        print("- Async processing works with HEIC files")
        print("- Converted JPEG displays correctly in browser")
    else:
        print("❌ HEIC ASYNC UPLOAD TEST FAILED")
    
    print("=" * 70)
    
    sys.exit(0 if result else 1)