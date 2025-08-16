#!/usr/bin/env python
"""Test script to verify OCR cache is working after the fix"""

import os
import sys
import django
import logging
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'receipt_splitter.settings')
django.setup()

# Configure logging to see cache messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from receipts.ocr_service import process_receipt_with_ocr, get_ocr_instance

def test_cache():
    """Test that the cache persists between calls"""
    
    # Load test image - use a known valid JPG
    test_image_path = Path("/home/kuitang/git/receipt-splitter/media/receipts/test_receipt.jpg")
    if not test_image_path.exists():
        print("Error: test_receipt.jpg not found")
        return
    
    with open(test_image_path, 'rb') as f:
        image_bytes = f.read()
    
    print("\n=== Testing OCR Cache Fix ===\n")
    
    # First call - should be a cache MISS
    print("1. First call (expecting cache MISS):")
    result1 = process_receipt_with_ocr(image_bytes, format_hint="JPEG")
    
    # Get cache stats after first call
    ocr = get_ocr_instance()
    if ocr:
        stats = ocr.get_cache_stats()
        print(f"   Cache stats: Hits={stats['cache_hits']}, Misses={stats['cache_misses']}, Hit Rate={stats['hit_rate']}%")
    
    # Second call with same image - should be a cache HIT
    print("\n2. Second call with same image (expecting cache HIT):")
    result2 = process_receipt_with_ocr(image_bytes, format_hint="PNG")
    
    # Get cache stats after second call
    if ocr:
        stats = ocr.get_cache_stats()
        print(f"   Cache stats: Hits={stats['cache_hits']}, Misses={stats['cache_misses']}, Hit Rate={stats['hit_rate']}%")
    
    # Third call with same image - should be another cache HIT
    print("\n3. Third call with same image (expecting cache HIT):")
    result3 = process_receipt_with_ocr(image_bytes, format_hint="PNG")
    
    # Final cache stats
    if ocr:
        stats = ocr.get_cache_stats()
        print(f"   Cache stats: Hits={stats['cache_hits']}, Misses={stats['cache_misses']}, Hit Rate={stats['hit_rate']}%")
        
        # Check if cache is working
        if stats['cache_hits'] >= 2:
            print("\n✅ SUCCESS: Cache is working! Multiple cache hits detected.")
        else:
            print("\n❌ FAILURE: Cache is not working. Expected at least 2 cache hits.")
            
        # Show cache info
        cache_info = stats.get('cache_info')
        if cache_info:
            print(f"\nCache info: {cache_info}")
    
    print("\n=== Test Complete ===\n")

if __name__ == "__main__":
    test_cache()