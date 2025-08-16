#!/usr/bin/env python3
"""
End-to-end test of balance validation with real receipt
"""

import os
import sys
import time
import json
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
from receipts.models import Receipt


def test_real_receipt_validation():
    """Test balance validation with a real receipt upload"""
    
    print("=" * 70)
    print("E2E BALANCE VALIDATION TEST")
    print("=" * 70)
    
    client = Client()
    
    # Clean up previous test receipts
    Receipt.objects.filter(uploader_name='Balance Test User').delete()
    
    # Create a simple test image
    print("\n1️⃣  Creating test receipt...")
    
    # Create a simple test image (1x1 white pixel)
    image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xaeB`\x82'
    
    uploaded_file = SimpleUploadedFile(
        name='test_receipt.png',
        content=image_data,
        content_type='image/png'
    )
    
    # Upload receipt
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'Balance Test User'
    })
    
    if response.status_code != 302:
        print(f"   ❌ Upload failed with status {response.status_code}")
        return False
    
    # Get the created receipt
    receipt = Receipt.objects.filter(uploader_name='Balance Test User').latest('created_at')
    print(f"   ✅ Receipt created with ID: {receipt.id}")
    
    # Wait for processing
    print("\n2️⃣  Waiting for processing...")
    max_wait = 5
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        receipt.refresh_from_db()
        if receipt.processing_status in ['completed', 'failed']:
            break
        time.sleep(0.5)
    
    print(f"   Processing status: {receipt.processing_status}")
    
    # Set session for authorization
    session = client.session
    session['receipt_id'] = str(receipt.id)
    session.save()
    
    # Test 3: Create an unbalanced receipt
    print("\n3️⃣  Creating unbalanced receipt data...")
    
    unbalanced_data = {
        'restaurant_name': 'Test Restaurant',
        'subtotal': 100.00,
        'tax': 10.00,
        'tip': 15.00,
        'total': 120.00,  # Wrong! Should be 125.00
        'items': [
            {'name': 'Pizza', 'quantity': 2, 'unit_price': 25.00, 'total_price': 50.00},
            {'name': 'Salad', 'quantity': 1, 'unit_price': 15.00, 'total_price': 15.00},
            {'name': 'Drinks', 'quantity': 5, 'unit_price': 7.00, 'total_price': 35.00}
        ]
    }
    
    # Update with unbalanced data
    response = client.post(
        f'/update/{receipt.id}/',
        data=json.dumps(unbalanced_data),
        content_type='application/json'
    )
    
    if response.status_code == 200:
        data = response.json()
        if not data.get('is_balanced'):
            print(f"   ✅ Backend detected unbalanced receipt")
            errors = data.get('validation_errors', {})
            if 'total' in errors:
                print(f"   Error: {errors['total']}")
        else:
            print(f"   ❌ Backend should have detected imbalance")
            receipt.delete()
            return False
    
    # Test 4: Try to finalize the unbalanced receipt
    print("\n4️⃣  Attempting to finalize unbalanced receipt...")
    
    response = client.post(f'/finalize/{receipt.id}/')
    
    if response.status_code == 400:
        data = response.json()
        print(f"   ✅ Finalization blocked: {data.get('error', '').split('.')[0]}")
    else:
        print(f"   ❌ Finalization should have been blocked")
        receipt.delete()
        return False
    
    # Test 5: Fix the balance
    print("\n5️⃣  Fixing the balance...")
    
    balanced_data = unbalanced_data.copy()
    balanced_data['total'] = 125.00  # Correct total
    
    response = client.post(
        f'/update/{receipt.id}/',
        data=json.dumps(balanced_data),
        content_type='application/json'
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('is_balanced'):
            print(f"   ✅ Receipt is now balanced")
        else:
            print(f"   ❌ Receipt should be balanced")
            print(f"   Errors: {data.get('validation_errors')}")
            receipt.delete()
            return False
    
    # Test 6: Finalize the balanced receipt
    print("\n6️⃣  Finalizing balanced receipt...")
    
    response = client.post(f'/finalize/{receipt.id}/')
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            print(f"   ✅ Receipt finalized successfully")
            print(f"   Share URL: {data.get('share_url')}")
        else:
            print(f"   ❌ Finalization failed")
            receipt.delete()
            return False
    else:
        print(f"   ❌ Finalization failed with status {response.status_code}")
        receipt.delete()
        return False
    
    # Test 7: Verify finalized receipt can't be edited
    print("\n7️⃣  Verifying finalized receipt is locked...")
    
    response = client.post(
        f'/update/{receipt.id}/',
        data=json.dumps(balanced_data),
        content_type='application/json'
    )
    
    if response.status_code == 400:
        data = response.json()
        if 'finalized' in data.get('error', '').lower():
            print(f"   ✅ Finalized receipt cannot be edited")
        else:
            print(f"   ⚠️  Unexpected error: {data.get('error')}")
    else:
        print(f"   ❌ Should not be able to edit finalized receipt")
        receipt.delete()
        return False
    
    # Clean up
    receipt.delete()
    print("\n🧹 Test data cleaned up")
    
    return True


def test_ui_validation_display():
    """Test that validation errors are displayed in the UI"""
    
    print("\n" + "=" * 70)
    print("UI VALIDATION DISPLAY TEST")
    print("=" * 70)
    
    client = Client()
    
    # Clean up
    Receipt.objects.filter(uploader_name='UI Validation Test').delete()
    
    # Create a receipt
    print("\n1️⃣  Creating test receipt for UI validation...")
    
    receipt = Receipt.objects.create(
        uploader_name='UI Validation Test',
        restaurant_name='UI Test Restaurant',
        date=django.utils.timezone.now(),
        subtotal=Decimal('50.00'),
        tax=Decimal('5.00'),
        tip=Decimal('10.00'),
        total=Decimal('65.00'),
        processing_status='completed',
        expires_at=django.utils.timezone.now() + django.utils.timezone.timedelta(days=30)
    )
    
    print(f"   ✅ Created receipt {receipt.id}")
    
    # Set session
    session = client.session
    session['receipt_id'] = str(receipt.id)
    session.save()
    
    # Load the edit page
    print("\n2️⃣  Loading edit page...")
    
    response = client.get(f'/edit/{receipt.id}/')
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Check for validation elements
        checks = {
            'Balance warning div': 'id="balance-warning"' in content,
            'Error details div': 'id="balance-error-details"' in content,
            'Validation function': 'validateReceipt()' in content,
            'Balance check function': 'checkAndDisplayBalance()' in content,
            'Receipt is balanced variable': 'receiptIsBalanced' in content,
        }
        
        all_present = True
        for check, present in checks.items():
            status = "✅" if present else "❌"
            print(f"   {status} {check}")
            if not present:
                all_present = False
        
        if not all_present:
            print("   ❌ Some UI validation elements missing")
            receipt.delete()
            return False
    else:
        print(f"   ❌ Failed to load edit page: {response.status_code}")
        receipt.delete()
        return False
    
    # Clean up
    receipt.delete()
    print("\n🧹 Test data cleaned up")
    
    return True


if __name__ == '__main__':
    print("\n🧪 RUNNING END-TO-END BALANCE VALIDATION TEST")
    print("=" * 70)
    
    all_passed = True
    
    # Run E2E test
    if not test_real_receipt_validation():
        all_passed = False
    
    # Run UI validation test
    if not test_ui_validation_display():
        all_passed = False
    
    print("\n" + "=" * 70)
    print("E2E TEST RESULTS")
    print("=" * 70)
    
    if all_passed:
        print("✅ ALL E2E BALANCE VALIDATION TESTS PASSED")
        print("\nFeatures verified:")
        print("- Unbalanced receipts cannot be finalized")
        print("- Balance errors are detected and reported")
        print("- Fixed receipts can be finalized")
        print("- Finalized receipts are locked")
        print("- UI validation elements are present")
    else:
        print("❌ SOME E2E TESTS FAILED")
    
    print("=" * 70)
    
    sys.exit(0 if all_passed else 1)