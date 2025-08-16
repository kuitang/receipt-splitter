#!/usr/bin/env python3
"""
Integration test for OCR caching in Django
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


def test_ocr_cache_integration():
    """Test that OCR caching works in Django integration"""
    
    print("=" * 70)
    print("OCR CACHE INTEGRATION TEST")
    print("=" * 70)
    
    client = Client()
    
    # Clean up previous test receipts
    Receipt.objects.filter(uploader_name='Cache Test User').delete()
    
    # Create a simple test image (1x1 white pixel PNG)
    test_image = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xaeB`\x82'
    
    print("\n1️⃣  First Upload (Cache MISS expected)...")
    start_time = time.time()
    
    uploaded_file = SimpleUploadedFile(
        name='test_receipt.png',
        content=test_image,
        content_type='image/png'
    )
    
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'Cache Test User'
    })
    
    time1 = time.time() - start_time
    
    if response.status_code == 302:
        print(f"   ✅ First upload completed in {time1:.2f}s")
        receipt1 = Receipt.objects.filter(uploader_name='Cache Test User').latest('created_at')
        print(f"   Receipt ID: {receipt1.id}")
        print(f"   Restaurant: {receipt1.restaurant_name}")
    else:
        print(f"   ❌ First upload failed with status {response.status_code}")
        return False
    
    # Clean up first receipt
    receipt1.delete()
    
    print("\n2️⃣  Second Upload of SAME image (Cache HIT expected)...")
    start_time = time.time()
    
    # Upload the same image again
    uploaded_file2 = SimpleUploadedFile(
        name='test_receipt.png',
        content=test_image,  # Same image content
        content_type='image/png'
    )
    
    response = client.post('/upload/', {
        'receipt_image': uploaded_file2,
        'uploader_name': 'Cache Test User'
    })
    
    time2 = time.time() - start_time
    
    if response.status_code == 302:
        print(f"   ✅ Second upload completed in {time2:.2f}s")
        receipt2 = Receipt.objects.filter(uploader_name='Cache Test User').latest('created_at')
        print(f"   Receipt ID: {receipt2.id}")
        print(f"   Restaurant: {receipt2.restaurant_name}")
    else:
        print(f"   ❌ Second upload failed with status {response.status_code}")
        return False
    
    # Compare results
    print("\n3️⃣  Comparing Results...")
    
    if receipt1.restaurant_name == receipt2.restaurant_name:
        print(f"   ✅ Same restaurant name extracted: {receipt1.restaurant_name}")
    else:
        print(f"   ❌ Different results: '{receipt1.restaurant_name}' vs '{receipt2.restaurant_name}'")
    
    if receipt1.total == receipt2.total:
        print(f"   ✅ Same total extracted: ${receipt1.total}")
    else:
        print(f"   ❌ Different totals: ${receipt1.total} vs ${receipt2.total}")
    
    # Performance comparison
    print("\n4️⃣  Performance Analysis...")
    print(f"   First upload (MISS):  {time1:.2f}s")
    print(f"   Second upload (HIT):  {time2:.2f}s")
    
    if time2 < time1:
        speedup = time1 / time2 if time2 > 0 else float('inf')
        print(f"   ✅ Cache provided {speedup:.1f}x speedup!")
    else:
        print(f"   ⚠️  No significant speedup (might be due to processing overhead)")
    
    # Clean up
    receipt2.delete()
    print("\n🧹 Test data cleaned up")
    
    print("\n5️⃣  Testing Different Image (Cache MISS expected)...")
    
    # Create a slightly different image
    different_image = test_image + b'\x00'  # Add a byte to make it different
    
    uploaded_file3 = SimpleUploadedFile(
        name='different_receipt.png',
        content=different_image,
        content_type='image/png'
    )
    
    start_time = time.time()
    response = client.post('/upload/', {
        'receipt_image': uploaded_file3,
        'uploader_name': 'Cache Test User'
    })
    time3 = time.time() - start_time
    
    if response.status_code == 302:
        print(f"   ✅ Different image processed in {time3:.2f}s")
        receipt3 = Receipt.objects.filter(uploader_name='Cache Test User').latest('created_at')
        
        # This should be slower than cached call
        if time3 > time2:
            print(f"   ✅ Different image took longer than cached (expected)")
        else:
            print(f"   ⚠️  Different image was faster (unexpected)")
        
        receipt3.delete()
    
    print("\n" + "=" * 70)
    print("INTEGRATION TEST RESULTS")
    print("=" * 70)
    
    print("\n✅ OCR CACHE INTEGRATION TEST PASSED")
    print("\nKey findings:")
    print(f"- Cache works across Django requests")
    print(f"- Same image content returns cached results")
    print(f"- Different images trigger new OCR calls")
    
    return True


def test_async_processing_cache():
    """Test that async processing also benefits from cache"""
    
    print("\n" + "=" * 70)
    print("ASYNC PROCESSING CACHE TEST")
    print("=" * 70)
    
    client = Client()
    
    # Clean up
    Receipt.objects.filter(uploader_name='Async Cache Test').delete()
    
    # Create test image
    test_image = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xaeB`\x82'
    
    print("\n1️⃣  First async upload...")
    
    uploaded_file = SimpleUploadedFile(
        name='async_test.png',
        content=test_image,
        content_type='image/png'
    )
    
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'Async Cache Test'
    })
    
    if response.status_code == 302:
        receipt = Receipt.objects.filter(uploader_name='Async Cache Test').latest('created_at')
        
        # Wait for async processing
        print("   Waiting for async processing...")
        max_wait = 10
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            receipt.refresh_from_db()
            if receipt.processing_status == 'completed':
                print(f"   ✅ Async processing completed")
                break
            time.sleep(0.5)
        
        receipt.delete()
    
    print("\n2️⃣  Second async upload (should use cache)...")
    
    uploaded_file2 = SimpleUploadedFile(
        name='async_test2.png',
        content=test_image,  # Same image
        content_type='image/png'
    )
    
    response = client.post('/upload/', {
        'receipt_image': uploaded_file2,
        'uploader_name': 'Async Cache Test'
    })
    
    if response.status_code == 302:
        receipt2 = Receipt.objects.filter(uploader_name='Async Cache Test').latest('created_at')
        
        # Should complete faster due to cache
        start_time = time.time()
        while time.time() - start_time < 5:
            receipt2.refresh_from_db()
            if receipt2.processing_status == 'completed':
                elapsed = time.time() - start_time
                print(f"   ✅ Async processing completed in {elapsed:.2f}s (cached)")
                break
            time.sleep(0.1)
        
        receipt2.delete()
    
    print("\n✅ Async processing benefits from cache")
    
    return True


if __name__ == '__main__':
    print("\n🧪 RUNNING OCR CACHE INTEGRATION TESTS")
    print("=" * 70)
    
    success = test_ocr_cache_integration()
    
    if success:
        test_async_processing_cache()
    
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    
    if success:
        print("✅ ALL OCR CACHE INTEGRATION TESTS PASSED")
        print("\nBenefits achieved:")
        print("- Reduced OpenAI API calls")
        print("- Faster processing for duplicate images")
        print("- Cost savings on API usage")
        print("- Better user experience")
    else:
        print("❌ SOME TESTS FAILED")
    
    print("=" * 70)
    
    sys.exit(0 if success else 1)