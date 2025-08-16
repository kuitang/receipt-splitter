#!/usr/bin/env python
"""Test that the JavaScript fixes are working correctly."""

import requests
import re

def test_static_file():
    """Test that receipt-editor.js is served correctly."""
    response = requests.get('http://localhost:8000/static/js/receipt-editor.js')
    if response.status_code == 200:
        print("✅ receipt-editor.js is served correctly")
        # Check for key functions
        content = response.text
        functions = [
            'calculateSubtotal',
            'updateSubtotal', 
            'removeItem',
            'attachItemListeners',
            'window.receiptIsBalanced'
        ]
        for func in functions:
            if func in content:
                print(f"  ✓ Found {func}")
            else:
                print(f"  ✗ Missing {func}")
    else:
        print(f"❌ receipt-editor.js returned status {response.status_code}")
    
def test_edit_page():
    """Test that the edit page loads without errors."""
    # First get a receipt ID from the index
    response = requests.get('http://localhost:8000/')
    if response.status_code == 200:
        # Find a receipt link
        match = re.search(r'/edit/([a-f0-9-]+)/', response.text)
        if match:
            receipt_id = match.group(1)
            edit_url = f'http://localhost:8000/edit/{receipt_id}/'
            response = requests.get(edit_url)
            if response.status_code == 200:
                print(f"✅ Edit page loads successfully for receipt {receipt_id}")
                # Check for our script tag
                if 'receipt-editor.js' in response.text:
                    print("  ✓ receipt-editor.js is included")
                if 'attachItemListeners' in response.text:
                    print("  ✓ attachItemListeners is called")
            else:
                print(f"❌ Edit page returned status {response.status_code}")
        else:
            print("⚠️ No receipts found to test")
    else:
        print(f"❌ Index page returned status {response.status_code}")

if __name__ == "__main__":
    print("Testing JavaScript fixes...")
    print("-" * 40)
    test_static_file()
    print("-" * 40)
    test_edit_page()
    print("-" * 40)
    print("Done!")