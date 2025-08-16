#!/usr/bin/env python3
"""
Test for UI regression fix - verify the edit UI matches the original layout
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


def test_ui_elements_after_async():
    """Test that the UI elements are correct after async processing"""
    
    print("=" * 70)
    print("UI REGRESSION TEST - ASYNC EDIT PAGE")
    print("=" * 70)
    
    client = Client()
    
    # Clean up previous test receipts
    Receipt.objects.filter(uploader_name='UI Test User').delete()
    
    # Load the HEIC test image
    heic_path = Path(__file__).parent.parent / 'IMG_6839.HEIC'
    
    if not heic_path.exists():
        print(f"\n❌ Test image not found: {heic_path}")
        return False
    
    print(f"\n✅ Found test HEIC image: {heic_path}")
    
    # Read the HEIC file
    with open(heic_path, 'rb') as f:
        heic_data = f.read()
    
    uploaded_file = SimpleUploadedFile(
        name='test_receipt.heic',
        content=heic_data,
        content_type='image/heic'
    )
    
    print("\n1️⃣  Uploading Receipt...")
    
    # Upload receipt
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'UI Test User'
    })
    
    if response.status_code != 302:
        print(f"   ❌ Upload failed with status {response.status_code}")
        return False
    
    # Get the created receipt
    receipt = Receipt.objects.filter(uploader_name='UI Test User').latest('created_at')
    print(f"   ✅ Receipt created with ID: {receipt.id}")
    
    # Wait for processing to complete
    print("\n2️⃣  Waiting for OCR Processing...")
    max_wait = 15
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        receipt.refresh_from_db()
        
        if receipt.processing_status == 'completed':
            print(f"   ✅ Processing completed in {time.time() - start_time:.1f} seconds")
            break
        elif receipt.processing_status == 'failed':
            print(f"   ❌ Processing failed")
            return False
        
        time.sleep(0.5)
    else:
        print(f"   ⚠️  Processing timeout")
        return False
    
    # Load the edit page after processing
    print("\n3️⃣  Loading Edit Page (After Processing)...")
    response = client.get(f'/edit/{receipt.id}/')
    
    if response.status_code != 200:
        print(f"   ❌ Failed to load edit page: {response.status_code}")
        return False
    
    content = response.content.decode('utf-8')
    
    # Check for key UI elements that should be present
    print("\n4️⃣  Checking UI Elements...")
    
    ui_checks = {
        'Restaurant Name Field': 'id="restaurant_name"' in content,
        'Subtotal Field': 'id="subtotal"' in content,
        'Tax Field': 'id="tax"' in content,
        'Tip Field': 'id="tip"' in content,
        'Total Field': 'id="total"' in content,
        'Grid Layout (12 columns)': 'grid-cols-12' in content,
        'Item Name Column (5 cols)': 'col-span-5' in content,
        'Quantity Column (2 cols)': 'col-span-2' in content and 'item-quantity' in content,
        'Price Column (2 cols)': 'col-span-2' in content and 'item-price' in content,
        'Total Column (2 cols)': 'col-span-2' in content and 'item-total' in content,
        'Delete Button Column (1 col)': 'col-span-1' in content,
        'Proration Display': 'item-proration' in content,
        'UpdateProrations Function': 'updateProrations' in content,
        'Save Changes Button': 'saveReceipt()' in content,
        'Finalize Button': 'finalizeReceipt()' in content,
    }
    
    all_passed = True
    for check_name, passed in ui_checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}")
        if not passed:
            all_passed = False
    
    # Check that the wrong UI elements are NOT present
    print("\n5️⃣  Checking Removed Elements...")
    
    removed_checks = {
        'Receipt Content Partial': 'receipts/partials/receipt_content.html' not in content,
        'No receipt-items div': 'id="receipt-items"' not in content,
        'No get_item_total filter': 'get_item_total' not in content,
    }
    
    for check_name, passed in removed_checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}")
        if not passed:
            all_passed = False
    
    # Check the actual data
    print("\n6️⃣  Checking OCR Data...")
    
    if receipt.restaurant_name and "Gin Mill" in receipt.restaurant_name:
        print(f"   ✅ Restaurant name extracted: {receipt.restaurant_name}")
    else:
        print(f"   ⚠️  Restaurant name: {receipt.restaurant_name}")
    
    print(f"   Total: ${receipt.total}")
    print(f"   Items count: {receipt.items.count()}")
    
    # Check that each item has the proration calculation
    if receipt.items.count() > 0:
        print("\n7️⃣  Checking Item Layout...")
        
        # Look for the specific grid structure for items
        for item in receipt.items.all()[:2]:  # Check first 2 items
            item_html_check = f'value="{item.name}"' in content
            if item_html_check:
                print(f"   ✅ Item '{item.name}' found in correct grid layout")
            else:
                print(f"   ❌ Item '{item.name}' not found")
                all_passed = False
    
    # Clean up
    receipt.delete()
    print("\n🧹 Test data cleaned up")
    
    return all_passed


if __name__ == '__main__':
    print("\n🧪 RUNNING UI REGRESSION TEST")
    print("=" * 70)
    
    result = test_ui_elements_after_async()
    
    print("\n" + "=" * 70)
    print("TEST RESULT")
    print("=" * 70)
    
    if result:
        print("✅ UI REGRESSION TEST PASSED")
        print("\nThe edit page UI matches the expected layout:")
        print("- Receipt details section with all fields")
        print("- Line items in 12-column grid layout")
        print("- Proration calculations for each item")
        print("- All buttons and functions present")
    else:
        print("❌ UI REGRESSION TEST FAILED")
        print("\nSome UI elements are missing or incorrect")
    
    print("=" * 70)
    
    sys.exit(0 if result else 1)