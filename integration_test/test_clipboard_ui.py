#!/usr/bin/env python3
"""
Test clipboard icon UI improvements
"""

import os
import sys
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
from io import BytesIO


def test_clipboard_icons():
    """Test that clipboard icons are present in the UI"""
    
    print("=" * 70)
    print("CLIPBOARD ICON UI TEST")
    print("=" * 70)
    
    client = Client()
    
    # Clean up previous test receipts
    Receipt.objects.filter(uploader_name='Clipboard Test User').delete()
    
    # Create a test image
    img = Image.new('RGB', (100, 100), color='white')
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    
    uploaded_file = SimpleUploadedFile(
        name='test_receipt.jpg',
        content=img_bytes.getvalue(),
        content_type='image/jpeg'
    )
    
    print("\n1️⃣  Creating Test Receipt...")
    
    # Upload receipt
    response = client.post('/upload/', {
        'receipt_image': uploaded_file,
        'uploader_name': 'Clipboard Test User'
    })
    
    if response.status_code != 302:
        print(f"   ❌ Upload failed with status {response.status_code}")
        return False
    
    # Get the created receipt
    receipt = Receipt.objects.filter(uploader_name='Clipboard Test User').first()
    print(f"   ✅ Receipt created with ID: {receipt.id}")
    
    # Wait for processing to complete (or timeout)
    import time
    max_wait = 5
    start_time = time.time()
    while time.time() - start_time < max_wait:
        receipt.refresh_from_db()
        if receipt.processing_status == 'completed':
            break
        time.sleep(0.5)
    
    # Finalize the receipt
    print("\n2️⃣  Finalizing Receipt...")
    
    response = client.post(f'/finalize/{receipt.id}/')
    if response.status_code == 200:
        print("   ✅ Receipt finalized successfully")
    else:
        print(f"   ❌ Failed to finalize: {response.status_code}")
        return False
    
    # Test 1: Check view page for uploader
    print("\n3️⃣  Testing View Page (Uploader's View)...")
    
    response = client.get(f'/r/{receipt.id}/')
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Check for clipboard icon SVG
        has_clipboard_icon = 'M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z' in content
        has_share_link_input = 'share-link-input' in content
        has_copy_function = 'copyShareUrl' in content
        
        if has_clipboard_icon:
            print("   ✅ Clipboard icon present in view page")
        else:
            print("   ❌ Clipboard icon missing in view page")
            
        if has_share_link_input:
            print("   ✅ Share link input field present")
        else:
            print("   ❌ Share link input field missing")
            
        if has_copy_function:
            print("   ✅ Copy function defined")
        else:
            print("   ❌ Copy function missing")
            
        view_page_passed = has_clipboard_icon and has_share_link_input and has_copy_function
    else:
        print(f"   ❌ Failed to load view page: {response.status_code}")
        view_page_passed = False
    
    # Test 2: Check edit page modal (create a new receipt for this)
    print("\n4️⃣  Testing Edit Page Modal...")
    
    # Create another receipt that's not finalized
    uploaded_file2 = SimpleUploadedFile(
        name='test_receipt2.jpg',
        content=img_bytes.getvalue(),
        content_type='image/jpeg'
    )
    
    response = client.post('/upload/', {
        'receipt_image': uploaded_file2,
        'uploader_name': 'Clipboard Test User 2'
    })
    
    receipt2 = Receipt.objects.filter(uploader_name='Clipboard Test User 2').first()
    
    # Wait for processing
    max_wait = 5
    start_time = time.time()
    while time.time() - start_time < max_wait:
        receipt2.refresh_from_db()
        if receipt2.processing_status == 'completed':
            break
        time.sleep(0.5)
    
    response = client.get(f'/edit/{receipt2.id}/')
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Check for clipboard icon in modal
        has_modal_icon = 'M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z' in content
        has_share_modal = 'share-modal' in content
        has_improved_copy = 'navigator.clipboard.writeText' in content
        
        if has_modal_icon:
            print("   ✅ Clipboard icon present in modal")
        else:
            print("   ❌ Clipboard icon missing in modal")
            
        if has_share_modal:
            print("   ✅ Share modal present")
        else:
            print("   ❌ Share modal missing")
            
        if has_improved_copy:
            print("   ✅ Modern clipboard API used")
        else:
            print("   ❌ Modern clipboard API not used")
            
        edit_page_passed = has_modal_icon and has_share_modal and has_improved_copy
    else:
        print(f"   ❌ Failed to load edit page: {response.status_code}")
        edit_page_passed = False
    
    # Clean up
    receipt.delete()
    if 'receipt2' in locals():
        receipt2.delete()
    Receipt.objects.filter(uploader_name__startswith='Clipboard Test').delete()
    print("\n🧹 Test data cleaned up")
    
    return view_page_passed and edit_page_passed


if __name__ == '__main__':
    print("\n🧪 RUNNING CLIPBOARD ICON UI TESTS")
    print("=" * 70)
    
    result = test_clipboard_icons()
    
    print("\n" + "=" * 70)
    print("TEST RESULT")
    print("=" * 70)
    
    if result:
        print("✅ CLIPBOARD UI TEST PASSED")
        print("\nKey improvements:")
        print("- Clipboard icon added to uploader's share link view")
        print("- Copy button replaced with clipboard icon in modal")
        print("- Modern clipboard API with fallback")
        print("- Visual feedback on copy action")
    else:
        print("❌ CLIPBOARD UI TEST FAILED")
    
    print("=" * 70)
    
    sys.exit(0 if result else 1)