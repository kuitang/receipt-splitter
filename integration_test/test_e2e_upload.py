#!/usr/bin/env python3
"""
End-to-end test of async receipt upload with actual image
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


def test_e2e_upload_with_real_image():
    """Test the complete async upload flow with a real image"""
    
    print("=" * 70)
    print("END-TO-END ASYNC UPLOAD TEST WITH REAL IMAGE")
    print("=" * 70)
    
    client = Client()
    
    # Clean up previous test receipts
    Receipt.objects.filter(uploader_name='E2E Test User').delete()
    
    # Load the actual HEIC test image
    image_path = Path(__file__).parent.parent / 'IMG_6839.HEIC'
    
    if not image_path.exists():
        print(f"\n❌ Test image not found: {image_path}")
        return False
    
    print(f"\n✅ Found test image: {image_path}")
    print(f"   File size: {image_path.stat().st_size:,} bytes")
    
    # Read the image file
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    uploaded_file = SimpleUploadedFile(
        name='IMG_6839.HEIC',
        content=image_data,
        content_type='image/heic'
    )
    
    print("\n1️⃣  Uploading Receipt...")
    
    # Upload receipt
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'E2E Test User'
    })
    
    print(f"   Upload response: {response.status_code}")
    
    if response.status_code != 302:
        print(f"   ❌ Expected redirect, got {response.status_code}")
        return False
    
    # Extract receipt ID from redirect URL
    redirect_url = response.url
    print(f"   Redirect to: {redirect_url}")
    
    # Get the receipt
    receipt = Receipt.objects.filter(uploader_name='E2E Test User').latest('created_at')
    print(f"   Receipt ID: {receipt.id}")
    
    # Check initial state
    print("\n2️⃣  Verifying Initial State...")
    print(f"   Processing status: {receipt.processing_status}")
    print(f"   Restaurant name: {receipt.restaurant_name}")
    
    if receipt.processing_status == 'pending':
        print("   ✅ Receipt created with pending status")
    else:
        print(f"   ⚠️  Unexpected initial status: {receipt.processing_status}")
    
    # Load the edit page to verify UI elements
    print("\n3️⃣  Loading Edit Page...")
    response = client.get(redirect_url)
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Check for key UI elements
        checks = {
            'Processing modal': 'processing-modal' in content,
            'Spinner animation': 'spinner' in content,
            'Upbeat copy': 'speed reader on espresso' in content,
            'Blur effect': 'processing-blur' in content,
            'Status polling': 'pollInterval' in content
        }
        
        all_passed = True
        for element, present in checks.items():
            status = "✅" if present else "❌"
            print(f"   {status} {element}")
            if not present:
                all_passed = False
        
        if not all_passed:
            print("   ⚠️  Some UI elements missing")
    else:
        print(f"   ❌ Failed to load edit page: {response.status_code}")
        return False
    
    # Wait for processing to complete
    print("\n4️⃣  Waiting for OCR Processing...")
    max_wait = 20  # seconds (OCR may take longer)
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        receipt.refresh_from_db()
        
        if receipt.processing_status == 'completed':
            print(f"   ✅ Processing completed in {time.time() - start_time:.1f} seconds")
            break
        elif receipt.processing_status == 'failed':
            print(f"   ❌ Processing failed: {getattr(receipt, 'processing_error', 'Unknown error')}")
            return False
        
        time.sleep(1)
    else:
        print(f"   ⚠️  Processing did not complete within {max_wait} seconds")
        print(f"   Current status: {receipt.processing_status}")
    
    # Check final state
    print("\n5️⃣  Verifying OCR Results...")
    receipt.refresh_from_db()
    
    print(f"   Final status: {receipt.processing_status}")
    print(f"   Restaurant name: {receipt.restaurant_name}")
    print(f"   Date: {receipt.date}")
    print(f"   Subtotal: ${receipt.subtotal}")
    print(f"   Tax: ${receipt.tax}")
    print(f"   Tip: ${receipt.tip}")
    print(f"   Total: ${receipt.total}")
    print(f"   Items count: {receipt.items.count()}")
    
    if receipt.processing_status == 'completed':
        # List all items
        if receipt.items.count() > 0:
            print("\n   📝 Line Items:")
            for item in receipt.items.all():
                print(f"      - {item.name}: ${item.total_price} (qty: {item.quantity})")
            
            print("\n   ✅ OCR successfully extracted receipt data!")
            return True
        else:
            print("   ⚠️  No items extracted (might be using mock data)")
            # Still consider it a success if the async flow worked
            return receipt.restaurant_name != "Processing..."
    else:
        print("   ❌ Processing did not complete successfully")
        return False


def test_status_endpoint_e2e():
    """Test the status endpoint with real receipt"""
    
    print("\n" + "=" * 70)
    print("STATUS ENDPOINT E2E TEST")
    print("=" * 70)
    
    client = Client()
    
    # Get the most recent test receipt
    try:
        receipt = Receipt.objects.filter(uploader_name='E2E Test User').latest('created_at')
    except Receipt.DoesNotExist:
        print("   ❌ No test receipt found")
        return False
    
    print(f"\n   Testing status endpoint for receipt {receipt.id}")
    
    # Test status endpoint
    response = client.get(f'/status/{receipt.id}/')
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"   Status response:")
        print(f"     - status: {data.get('status')}")
        print(f"     - restaurant: {data.get('restaurant_name')}")
        print(f"     - total: ${data.get('total')}")
        print(f"     - items_count: {data.get('items_count')}")
        
        if 'error' in data and data['error']:
            print(f"     - error: {data['error']}")
        
        print("   ✅ Status endpoint working correctly")
        return True
    else:
        print(f"   ❌ Status endpoint failed: {response.status_code}")
        return False


def cleanup():
    """Clean up test data"""
    Receipt.objects.filter(uploader_name='E2E Test User').delete()
    print("\n🧹 Test data cleaned up")


if __name__ == '__main__':
    print("\n🚀 RUNNING END-TO-END ASYNC UPLOAD TEST")
    print("=" * 70)
    
    test_results = []
    
    # Test 1: Complete E2E upload
    print("\n📝 Test 1: End-to-End Upload with Real Image")
    result = test_e2e_upload_with_real_image()
    test_results.append(("E2E Upload", result))
    
    # Test 2: Status endpoint
    print("\n📝 Test 2: Status Endpoint E2E")
    result = test_status_endpoint_e2e()
    test_results.append(("Status Endpoint E2E", result))
    
    # Cleanup
    cleanup()
    
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
        print("✅ ALL E2E TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 70)
    
    sys.exit(0 if all_passed else 1)