#!/usr/bin/env python3
"""
Integration tests for asynchronous receipt upload feature
"""

import os
import sys
import time
from pathlib import Path
from decimal import Decimal

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
from io import BytesIO


def create_test_image():
    """Create a simple test image"""
    img = Image.new('RGB', (100, 100), color='white')
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()


def test_async_upload_flow():
    """Test the complete async upload flow"""
    
    print("=" * 70)
    print("ASYNC UPLOAD FLOW TEST")
    print("=" * 70)
    
    client = Client()
    
    # Clean up previous test receipts
    Receipt.objects.filter(uploader_name='Async Test').delete()
    
    # Create test image
    image_data = create_test_image()
    uploaded_file = SimpleUploadedFile(
        name='test_receipt.jpg',
        content=image_data,
        content_type='image/jpeg'
    )
    
    print("\n1️⃣  Testing Receipt Upload...")
    
    # Upload receipt
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'Async Test'
    })
    
    print(f"   Upload response: {response.status_code}")
    
    if response.status_code != 302:
        print(f"   ❌ Expected redirect, got {response.status_code}")
        return False
    
    # Extract receipt ID from redirect URL
    redirect_url = response.url
    print(f"   Redirect to: {redirect_url}")
    
    # Get the receipt
    receipt = Receipt.objects.filter(uploader_name='Async Test').latest('created_at')
    print(f"   Receipt ID: {receipt.id}")
    
    # Check initial state
    print("\n2️⃣  Checking Initial State...")
    print(f"   Processing status: {receipt.processing_status}")
    print(f"   Restaurant name: {receipt.restaurant_name}")
    
    if receipt.processing_status == 'pending':
        print("   ✅ Receipt created with pending status")
    else:
        print(f"   ⚠️  Unexpected initial status: {receipt.processing_status}")
    
    # Follow redirect to edit page
    print("\n3️⃣  Loading Edit Page...")
    response = client.get(redirect_url)
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Check for processing modal
        if 'processing-modal' in content and 'Analyzing Your Receipt' in content:
            print("   ✅ Processing modal displayed")
        else:
            print("   ❌ Processing modal not found")
        
        # Check for blur effect
        if 'processing-blur' in content or 'isProcessing = true' in content:
            print("   ✅ Content blurred while processing")
        else:
            print("   ⚠️  Blur effect not applied")
    else:
        print(f"   ❌ Failed to load edit page: {response.status_code}")
        return False
    
    # Wait for processing to complete (with timeout)
    print("\n4️⃣  Waiting for Processing...")
    max_wait = 15  # seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        receipt.refresh_from_db()
        
        if receipt.processing_status == 'completed':
            print(f"   ✅ Processing completed in {time.time() - start_time:.1f} seconds")
            break
        elif receipt.processing_status == 'failed':
            print(f"   ❌ Processing failed: {receipt.processing_error}")
            break
        
        time.sleep(0.5)
    else:
        print(f"   ⚠️  Processing did not complete within {max_wait} seconds")
    
    # Check final state
    print("\n5️⃣  Checking Final State...")
    receipt.refresh_from_db()
    
    print(f"   Final status: {receipt.processing_status}")
    print(f"   Restaurant name: {receipt.restaurant_name}")
    print(f"   Items count: {receipt.items.count()}")
    
    if receipt.processing_status == 'completed':
        if receipt.restaurant_name != "Processing...":
            print("   ✅ Receipt data updated after processing")
        else:
            print("   ⚠️  Receipt data not updated")
        
        # Check if totals are valid
        if receipt.total > 0:
            print(f"   ✅ Receipt total: ${receipt.total}")
        
        return True
    else:
        print("   ❌ Processing did not complete successfully")
        return False


def test_status_endpoint():
    """Test the status checking endpoint"""
    
    print("\n" + "=" * 70)
    print("STATUS ENDPOINT TEST")
    print("=" * 70)
    
    client = Client()
    
    # Get or create a test receipt
    try:
        receipt = Receipt.objects.filter(uploader_name='Async Test').latest('created_at')
    except Receipt.DoesNotExist:
        # Create one
        receipt = Receipt.objects.create(
            uploader_name='Async Test',
            restaurant_name='Test Restaurant',
            date=django.utils.timezone.now(),
            subtotal=Decimal('10'),
            tax=Decimal('1'),
            tip=Decimal('2'),
            total=Decimal('13'),
            processing_status='completed'
        )
    
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
        
        if data.get('status') == receipt.processing_status:
            print("   ✅ Status endpoint working correctly")
            return True
        else:
            print("   ❌ Status mismatch")
            return False
    else:
        print(f"   ❌ Status endpoint failed: {response.status_code}")
        return False


def test_processing_ui_elements():
    """Test that UI elements are properly rendered"""
    
    print("\n" + "=" * 70)
    print("UI ELEMENTS TEST")
    print("=" * 70)
    
    client = Client()
    
    # Create a processing receipt
    receipt = Receipt.objects.create(
        uploader_name='UI Test',
        restaurant_name='Processing...',
        date=django.utils.timezone.now(),
        subtotal=Decimal('0'),
        tax=Decimal('0'),
        tip=Decimal('0'),
        total=Decimal('0'),
        processing_status='processing'
    )
    
    # Set session
    session = client.session
    session['uploader_name'] = 'UI Test'
    session['receipt_id'] = str(receipt.id)
    session.save()
    
    # Load edit page
    response = client.get(f'/edit/{receipt.id}/')
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        ui_elements = {
            'Spinner animation': 'spinner' in content,
            'Processing modal': 'processing-modal' in content,
            'Upbeat copy': 'speed reader on espresso' in content,
            'Blur effect': 'processing-blur' in content,
            'Status polling': 'pollInterval' in content,
            'Disabled buttons': 'opacity-50 cursor-not-allowed' in content
        }
        
        print("\n   UI Elements Check:")
        all_present = True
        for element, present in ui_elements.items():
            status = "✅" if present else "❌"
            print(f"     {status} {element}")
            if not present:
                all_present = False
        
        # Cleanup
        receipt.delete()
        
        return all_present
    else:
        print(f"   ❌ Failed to load page: {response.status_code}")
        return False


def cleanup():
    """Clean up test data"""
    Receipt.objects.filter(uploader_name__in=['Async Test', 'UI Test']).delete()
    print("\n🧹 Test data cleaned up")


if __name__ == '__main__':
    print("\n🧪 RUNNING ASYNC UPLOAD INTEGRATION TESTS")
    print("=" * 70)
    
    test_results = []
    
    # Test 1: Complete async flow
    print("\n📝 Test 1: Async Upload Flow")
    result = test_async_upload_flow()
    test_results.append(("Async Upload Flow", result))
    
    # Test 2: Status endpoint
    print("\n📝 Test 2: Status Endpoint")
    result = test_status_endpoint()
    test_results.append(("Status Endpoint", result))
    
    # Test 3: UI elements
    print("\n📝 Test 3: Processing UI Elements")
    result = test_processing_ui_elements()
    test_results.append(("UI Elements", result))
    
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
        print("✅ ALL ASYNC UPLOAD TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 70)
    
    sys.exit(0 if all_passed else 1)