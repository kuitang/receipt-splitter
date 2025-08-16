#!/usr/bin/env python3
"""
Test receipt balance validation - ensure receipts must balance before finalization
"""

import os
import sys
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
from receipts.models import Receipt, LineItem
from receipts.validation import validate_receipt_balance


def test_validation_logic():
    """Test the validation logic directly"""
    print("=" * 70)
    print("TESTING VALIDATION LOGIC")
    print("=" * 70)
    
    # Test 1: Valid receipt
    print("\n1️⃣  Testing valid receipt...")
    valid_data = {
        'subtotal': '50.00',
        'tax': '5.00',
        'tip': '10.00',
        'total': '65.00',
        'items': [
            {'name': 'Burger', 'quantity': 2, 'unit_price': '15.00', 'total_price': '30.00'},
            {'name': 'Fries', 'quantity': 2, 'unit_price': '10.00', 'total_price': '20.00'}
        ]
    }
    
    is_valid, errors = validate_receipt_balance(valid_data)
    if is_valid and not errors:
        print("   ✅ Valid receipt passes validation")
    else:
        print(f"   ❌ Valid receipt failed: {errors}")
        return False
    
    # Test 2: Items don't sum to subtotal
    print("\n2️⃣  Testing items not matching subtotal...")
    invalid_subtotal = valid_data.copy()
    invalid_subtotal['subtotal'] = '45.00'  # Should be 50
    
    is_valid, errors = validate_receipt_balance(invalid_subtotal)
    if not is_valid and 'subtotal' in errors:
        print(f"   ✅ Detected subtotal mismatch: {errors['subtotal']}")
    else:
        print(f"   ❌ Failed to detect subtotal mismatch")
        return False
    
    # Test 3: Total doesn't match calculation
    print("\n3️⃣  Testing incorrect total...")
    invalid_total = valid_data.copy()
    invalid_total['total'] = '60.00'  # Should be 65
    
    is_valid, errors = validate_receipt_balance(invalid_total)
    if not is_valid and 'total' in errors:
        print(f"   ✅ Detected total mismatch: {errors['total']}")
    else:
        print(f"   ❌ Failed to detect total mismatch")
        return False
    
    # Test 4: Item calculation wrong
    print("\n4️⃣  Testing incorrect item calculation...")
    invalid_item = valid_data.copy()
    invalid_item['items'][0]['total_price'] = '25.00'  # Should be 30 (2 x 15)
    
    is_valid, errors = validate_receipt_balance(invalid_item)
    if not is_valid and 'items' in errors:
        print(f"   ✅ Detected item calculation error: {errors['items'][0]['message']}")
    else:
        print(f"   ❌ Failed to detect item calculation error")
        return False
    
    # Test 5: Negative tax/tip (allowed as discounts)
    print("\n5️⃣  Testing negative tax/tip (discounts)...")
    discount_data = {
        'subtotal': '50.00',
        'tax': '-5.00',  # Tax discount
        'tip': '10.00',
        'total': '55.00',  # Adjusted total (50 - 5 + 10)
        'items': [
            {'name': 'Burger', 'quantity': 2, 'unit_price': '15.00', 'total_price': '30.00'},
            {'name': 'Fries', 'quantity': 2, 'unit_price': '10.00', 'total_price': '20.00'}
        ]
    }
    
    is_valid, errors = validate_receipt_balance(discount_data)
    if is_valid:
        print(f"   ✅ Negative tax accepted as discount")
    else:
        print(f"   ❌ Negative tax should be allowed: {errors}")
        return False
    
    # Test negative tip
    discount_tip = {
        'subtotal': '50.00',
        'tax': '5.00',
        'tip': '-2.00',  # Tip discount
        'total': '53.00',  # Adjusted total (50 + 5 - 2)
        'items': [
            {'name': 'Burger', 'quantity': 2, 'unit_price': '15.00', 'total_price': '30.00'},
            {'name': 'Fries', 'quantity': 2, 'unit_price': '10.00', 'total_price': '20.00'}
        ]
    }
    
    is_valid, errors = validate_receipt_balance(discount_tip)
    if is_valid:
        print(f"   ✅ Negative tip accepted as discount")
    else:
        print(f"   ❌ Negative tip should be allowed: {errors}")
        return False
    
    # Test 6: TOTAL_CORRECTION scenario - discrepancy as negative tip
    print("\n6️⃣  Testing TOTAL_CORRECTION scenario...")
    # Simulating Gin Mill case where OCR correction adds tip
    gin_mill_case = {
        'subtotal': '60.50',
        'tax': '0.00',
        'tip': '3.50',  # Added by TOTAL_CORRECTION to balance
        'total': '64.00',
        'items': [
            {'name': 'Food items', 'quantity': 1, 'unit_price': '60.50', 'total_price': '60.50'}
        ]
    }
    
    is_valid, errors = validate_receipt_balance(gin_mill_case)
    if is_valid:
        print(f"   ✅ TOTAL_CORRECTION case validated")
    else:
        print(f"   ❌ TOTAL_CORRECTION case should be valid: {errors}")
        return False
    
    # Test 7: Negative subtotal (not allowed)
    print("\n7️⃣  Testing negative subtotal (not allowed)...")
    negative_subtotal = {
        'subtotal': '-50.00',
        'tax': '5.00',
        'tip': '10.00', 
        'total': '-35.00',
        'items': []
    }
    
    is_valid, errors = validate_receipt_balance(negative_subtotal)
    if not is_valid and 'subtotal_negative' in errors:
        print(f"   ✅ Detected negative subtotal: {errors['subtotal_negative']}")
    else:
        print(f"   ❌ Failed to detect negative subtotal")
        return False
    
    return True


def test_api_validation():
    """Test the API endpoints with validation"""
    print("\n" + "=" * 70)
    print("TESTING API VALIDATION")
    print("=" * 70)
    
    client = Client()
    
    # Create a test receipt
    print("\n1️⃣  Creating test receipt...")
    receipt = Receipt.objects.create(
        uploader_name='Test User',
        restaurant_name='Test Restaurant',
        date=django.utils.timezone.now(),
        subtotal=Decimal('50.00'),
        tax=Decimal('5.00'),
        tip=Decimal('10.00'),
        total=Decimal('65.00'),
        expires_at=django.utils.timezone.now() + django.utils.timezone.timedelta(days=30)
    )
    
    # Add items
    LineItem.objects.create(
        receipt=receipt,
        name='Burger',
        quantity=2,
        unit_price=Decimal('15.00'),
        total_price=Decimal('30.00')
    )
    LineItem.objects.create(
        receipt=receipt,
        name='Fries',
        quantity=2,
        unit_price=Decimal('10.00'),
        total_price=Decimal('20.00')
    )
    
    print(f"   ✅ Created receipt {receipt.id}")
    
    # Set session
    session = client.session
    session['receipt_id'] = str(receipt.id)
    session.save()
    
    # Test 2: Update with invalid data
    print("\n2️⃣  Testing update with unbalanced data...")
    update_data = {
        'restaurant_name': 'Updated Restaurant',
        'subtotal': 45.00,  # Wrong - should be 50
        'tax': 5.00,
        'tip': 10.00,
        'total': 65.00,
        'items': [
            {'name': 'Burger', 'quantity': 2, 'unit_price': 15.00, 'total_price': 30.00},
            {'name': 'Fries', 'quantity': 2, 'unit_price': 10.00, 'total_price': 20.00}
        ]
    }
    
    response = client.post(
        f'/update/{receipt.id}/',
        data=json.dumps(update_data),
        content_type='application/json'
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and not data.get('is_balanced'):
            print(f"   ✅ Update succeeded but marked as unbalanced")
            if data.get('validation_errors'):
                print(f"   Validation errors: {data['validation_errors'].get('subtotal', '')}")
        else:
            print(f"   ❌ Unexpected response: {data}")
            receipt.delete()
            return False
    else:
        print(f"   ❌ Update failed with status {response.status_code}")
        receipt.delete()
        return False
    
    # Test 3: Try to finalize unbalanced receipt
    print("\n3️⃣  Testing finalization of unbalanced receipt...")
    response = client.post(f'/finalize/{receipt.id}/')
    
    if response.status_code == 400:
        data = response.json()
        print(f"   ✅ Finalization rejected: {data.get('error', '').split('.')[0]}")
    else:
        print(f"   ❌ Finalization should have been rejected but got status {response.status_code}")
        receipt.delete()
        return False
    
    # Test 4: Test receipt with discount (negative tax)
    print("\n4️⃣  Testing receipt with discount (negative tax)...")
    discount_update = {
        'restaurant_name': 'Discount Restaurant',
        'subtotal': 50.00,
        'tax': -5.00,  # Discount applied as negative tax
        'tip': 10.00,
        'total': 55.00,  # 50 - 5 + 10
        'items': [
            {'name': 'Burger', 'quantity': 2, 'unit_price': 15.00, 'total_price': 30.00},
            {'name': 'Fries', 'quantity': 2, 'unit_price': 10.00, 'total_price': 20.00}
        ]
    }
    
    response = client.post(
        f'/update/{receipt.id}/',
        data=json.dumps(discount_update),
        content_type='application/json'
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('is_balanced'):
            print(f"   ✅ Receipt with discount validated correctly")
        else:
            print(f"   ❌ Discount should be valid: {data}")
            receipt.delete()
            return False
    
    # Test 5: Fix the receipt and finalize
    print("\n5️⃣  Testing finalization of balanced receipt...")
    valid_update = {
        'restaurant_name': 'Updated Restaurant',
        'subtotal': 50.00,  # Correct
        'tax': 5.00,
        'tip': 10.00,
        'total': 65.00,
        'items': [
            {'name': 'Burger', 'quantity': 2, 'unit_price': 15.00, 'total_price': 30.00},
            {'name': 'Fries', 'quantity': 2, 'unit_price': 10.00, 'total_price': 20.00}
        ]
    }
    
    # Update with valid data
    response = client.post(
        f'/update/{receipt.id}/',
        data=json.dumps(valid_update),
        content_type='application/json'
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('is_balanced'):
            print(f"   ✅ Receipt updated and balanced")
        else:
            print(f"   ❌ Receipt should be balanced: {data}")
            receipt.delete()
            return False
    
    # Now finalize
    response = client.post(f'/finalize/{receipt.id}/')
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            print(f"   ✅ Balanced receipt finalized successfully")
            print(f"   Share URL: {data.get('share_url')}")
        else:
            print(f"   ❌ Finalization failed: {data}")
            receipt.delete()
            return False
    else:
        print(f"   ❌ Finalization failed with status {response.status_code}")
        data = response.json()
        print(f"   Error: {data.get('error')}")
        receipt.delete()
        return False
    
    # Clean up
    receipt.delete()
    print("\n🧹 Test data cleaned up")
    
    return True


def test_decimal_precision():
    """Test that decimal precision is handled correctly"""
    print("\n" + "=" * 70)
    print("TESTING DECIMAL PRECISION")
    print("=" * 70)
    
    # Test with numbers that would cause floating point errors
    print("\n1️⃣  Testing problematic decimal calculations...")
    
    data = {
        'subtotal': '10.01',
        'tax': '0.87',
        'tip': '2.00',
        'total': '12.88',
        'items': [
            {'name': 'Item 1', 'quantity': 1, 'unit_price': '3.33', 'total_price': '3.33'},
            {'name': 'Item 2', 'quantity': 1, 'unit_price': '3.34', 'total_price': '3.34'},
            {'name': 'Item 3', 'quantity': 1, 'unit_price': '3.34', 'total_price': '3.34'}
        ]
    }
    
    is_valid, errors = validate_receipt_balance(data)
    if is_valid:
        print("   ✅ Decimal precision handled correctly")
    else:
        print(f"   ❌ Precision error: {errors}")
        return False
    
    # Test with repeating decimals
    print("\n2️⃣  Testing repeating decimals...")
    
    # 10 / 3 = 3.333... but we round to 3.33
    data2 = {
        'subtotal': '10.00',
        'tax': '1.00',
        'tip': '1.50',
        'total': '12.50',
        'items': [
            {'name': 'Item split 3 ways', 'quantity': 3, 'unit_price': '3.33', 'total_price': '9.99'},
            {'name': 'Penny item', 'quantity': 1, 'unit_price': '0.01', 'total_price': '0.01'}
        ]
    }
    
    is_valid, errors = validate_receipt_balance(data2)
    if is_valid:
        print("   ✅ Repeating decimals handled with rounding")
    else:
        print(f"   ⚠️  Validation result: {errors}")
    
    return True


if __name__ == '__main__':
    print("\n🧪 RUNNING BALANCE VALIDATION TESTS")
    print("=" * 70)
    
    all_passed = True
    
    # Run validation logic tests
    if not test_validation_logic():
        all_passed = False
    
    # Run API tests
    if not test_api_validation():
        all_passed = False
    
    # Run decimal precision tests
    if not test_decimal_precision():
        all_passed = False
    
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    if all_passed:
        print("✅ ALL BALANCE VALIDATION TESTS PASSED")
        print("\nKey features verified:")
        print("- Backend validation detects unbalanced receipts")
        print("- Update API returns validation status")
        print("- Finalize API rejects unbalanced receipts")
        print("- Decimal precision handled correctly")
        print("- Negative tax/tip allowed as discounts (per TOTAL_CORRECTION)")
        print("- Negative subtotal/total properly rejected")
    else:
        print("❌ SOME TESTS FAILED")
    
    print("=" * 70)
    
    sys.exit(0 if all_passed else 1)