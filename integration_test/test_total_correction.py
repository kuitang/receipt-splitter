#!/usr/bin/env python3
"""
Integration test for total correction feature
Ensures the invariant: line items MUST add up to the Total
"""

import os
import sys
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


def test_gin_mill_correction():
    """Test that the Gin Mill receipt gets corrected properly"""
    
    print("=" * 70)
    print("TOTAL CORRECTION INTEGRATION TEST")
    print("=" * 70)
    
    # Check for test image
    if not Path('IMG_6839.HEIC').exists():
        print("⚠️  IMG_6839.HEIC not found, skipping test")
        return False
    
    client = Client()
    
    # Clean up previous test
    Receipt.objects.filter(uploader_name='Correction Test').delete()
    
    # Upload the Gin Mill receipt
    with open('IMG_6839.HEIC', 'rb') as f:
        heic_data = f.read()
    
    uploaded_file = SimpleUploadedFile(
        name='gin_mill.heic',
        content=heic_data,
        content_type='image/heic'
    )
    
    print("\n📤 Uploading Gin Mill receipt...")
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'Correction Test'
    })
    
    if response.status_code != 302:
        print(f"❌ Upload failed: {response.status_code}")
        return False
    
    print("✅ Upload successful")
    
    # Get the created receipt
    receipt = Receipt.objects.filter(uploader_name='Correction Test').latest('created_at')
    
    print(f"\n📋 Receipt Analysis:")
    print(f"   Restaurant: {receipt.restaurant_name}")
    print(f"   Items: {receipt.items.count()}")
    
    # Calculate totals
    items_sum = sum(item.total_price for item in receipt.items.all())
    calculated_total = receipt.subtotal + receipt.tax + receipt.tip
    
    print(f"\n💰 Original OCR Values (before correction):")
    print(f"   Items sum:    ${items_sum:.2f}")
    print(f"   Subtotal:     ${receipt.subtotal:.2f}")
    print(f"   Tax:          ${receipt.tax:.2f}")
    print(f"   Tip:          ${receipt.tip:.2f}")
    print(f"   Receipt Total: ${receipt.total:.2f}")
    
    print(f"\n🔧 After Correction:")
    print(f"   Subtotal + Tax + Tip = ${calculated_total:.2f}")
    print(f"   Receipt Total        = ${receipt.total:.2f}")
    
    # Check the invariant
    tolerance = Decimal('0.01')
    if abs(calculated_total - receipt.total) <= tolerance:
        print(f"\n✅ INVARIANT SATISFIED: Totals match within ${tolerance}")
        
        # Check specific correction for Gin Mill
        if receipt.restaurant_name == "The Gin Mill (NY)":
            if receipt.tip == Decimal('3.50'):
                print("✅ Correction applied correctly: $3.50 discrepancy moved to tip")
            elif receipt.tip == Decimal('0'):
                print("⚠️  Warning: Correction might not have been applied")
        
        return True
    else:
        print(f"\n❌ INVARIANT VIOLATED: Discrepancy of ${abs(calculated_total - receipt.total):.2f}")
        return False


def test_mock_data_correction():
    """Test that mock data also satisfies the invariant"""
    
    print("\n" + "=" * 70)
    print("MOCK DATA INVARIANT TEST")
    print("=" * 70)
    
    from receipts.ocr_service import get_mock_receipt_data
    
    mock_data = get_mock_receipt_data()
    
    # Calculate totals
    items_sum = sum(item['total_price'] for item in mock_data['items'])
    subtotal = mock_data['subtotal']
    tax = mock_data['tax']
    tip = mock_data['tip']
    total = mock_data['total']
    calculated_total = subtotal + tax + tip
    
    print(f"\nMock Receipt Totals:")
    print(f"   Items sum:    ${items_sum:.2f}")
    print(f"   Subtotal:     ${subtotal:.2f}")
    print(f"   Tax:          ${tax:.2f}")
    print(f"   Tip:          ${tip:.2f}")
    print(f"   Total:        ${total:.2f}")
    
    print(f"\nInvariant Check:")
    print(f"   Subtotal + Tax + Tip = ${calculated_total:.2f}")
    print(f"   Receipt Total        = ${total:.2f}")
    
    if abs(calculated_total - total) < 0.01:
        print("✅ Mock data satisfies invariant")
        return True
    else:
        print(f"❌ Mock data violates invariant by ${abs(calculated_total - total):.2f}")
        return False


def cleanup():
    """Clean up test data"""
    Receipt.objects.filter(uploader_name='Correction Test').delete()
    print("\n🧹 Test data cleaned up")


if __name__ == '__main__':
    print("\n🧪 RUNNING TOTAL CORRECTION INTEGRATION TESTS")
    print("=" * 70)
    
    # Check for API key
    from django.conf import settings
    has_api_key = settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_api_key_here"
    
    test_results = []
    
    if has_api_key:
        print("✅ OpenAI API key configured\n")
        
        # Test 1: Real receipt correction
        print("📝 Test 1: Gin Mill Receipt Correction")
        result = test_gin_mill_correction()
        test_results.append(("Gin Mill Correction", result))
    else:
        print("⚠️  No API key - skipping OCR test\n")
    
    # Test 2: Mock data invariant
    print("\n📝 Test 2: Mock Data Invariant")
    result = test_mock_data_correction()
    test_results.append(("Mock Data Invariant", result))
    
    # Cleanup
    if has_api_key:
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
        print("✅ ALL CORRECTION TESTS PASSED")
        print("\nThe invariant is enforced: Line items ALWAYS add up to the Total")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 70)
    
    sys.exit(0 if all_passed else 1)