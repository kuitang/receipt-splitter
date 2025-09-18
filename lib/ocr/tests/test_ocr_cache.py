#!/usr/bin/env python3
"""
Test OCR caching functionality
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.ocr.ocr_lib import ReceiptOCR


TEST_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00'
    b'\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xaeB`\x82'
)


def test_ocr_cache():
    """Test that OCR caching works correctly"""
    
    print("=" * 70)
    print("TESTING OCR CACHE")
    print("=" * 70)
    
    # Get API key from environment
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key or api_key == "your_api_key_here":
        print("\n⚠️  OpenAI API key not configured, using mock test")
        print("Set OPENAI_API_KEY environment variable to test real caching")
        return test_mock_cache()
    
    # Initialize OCR with small cache for testing
    ocr = ReceiptOCR(api_key, cache_size=5)
    
    # Create a simple test image (1x1 white pixel PNG)
    test_image = TEST_PNG
    
    print("\n1️⃣  First call (should be a cache MISS)...")
    start_time = time.time()
    
    try:
        result1 = ocr.process_image_bytes(test_image)
        time1 = time.time() - start_time
        print(f"   ✅ First call completed in {time1:.2f}s")
        print(f"   Restaurant: {result1.restaurant_name}")
    except Exception as e:
        print(f"   ❌ First call failed: {e}")
        return False
    
    # Check cache stats
    stats = ocr.get_cache_stats()
    print(f"   Cache stats: Hits={stats['cache_hits']}, Misses={stats['cache_misses']}")
    
    if stats['cache_misses'] != 1:
        print(f"   ❌ Expected 1 cache miss, got {stats['cache_misses']}")
        return False
    
    print("\n2️⃣  Second call with same image (should be a cache HIT)...")
    start_time = time.time()
    
    try:
        result2 = ocr.process_image_bytes(test_image)
        time2 = time.time() - start_time
        print(f"   ✅ Second call completed in {time2:.2f}s")
        print(f"   Restaurant: {result2.restaurant_name}")
    except Exception as e:
        print(f"   ❌ Second call failed: {e}")
        return False
    
    # Check cache stats
    stats = ocr.get_cache_stats()
    print(f"   Cache stats: Hits={stats['cache_hits']}, Misses={stats['cache_misses']}")
    
    if stats['cache_hits'] != 1:
        print(f"   ❌ Expected 1 cache hit, got {stats['cache_hits']}")
        return False
    
    # Verify results are identical
    if result1.restaurant_name != result2.restaurant_name:
        print(f"   ❌ Results don't match!")
        return False
    
    # Check performance improvement
    speedup = time1 / time2 if time2 > 0 else float('inf')
    print(f"\n3️⃣  Performance Comparison:")
    print(f"   First call (MISS):  {time1:.3f}s")
    print(f"   Second call (HIT):  {time2:.3f}s")
    print(f"   Speedup:            {speedup:.1f}x faster")
    
    if time2 < time1:
        print(f"   ✅ Cache provided {speedup:.1f}x speedup!")
    else:
        print(f"   ⚠️  Cache hit was not faster (might be due to small image)")
    
    # Test cache eviction
    print("\n4️⃣  Testing cache eviction (cache size = 5)...")
    
    # Add 5 more different images to fill the cache
    for i in range(5):
        # Modify the image slightly to create different hashes
        modified_image = test_image + bytes([i])
        ocr.process_image_bytes(modified_image)
        print(f"   Added image {i+1} to cache")
    
    stats = ocr.get_cache_stats()
    print(f"   Cache stats: Hits={stats['cache_hits']}, Misses={stats['cache_misses']}")
    
    # Now the original image should be evicted
    print("\n5️⃣  Testing if original image was evicted...")
    ocr.process_image_bytes(test_image)
    
    stats_after = ocr.get_cache_stats()
    if stats_after['cache_misses'] > stats['cache_misses']:
        print(f"   ✅ Original image was evicted (cache miss occurred)")
    else:
        print(f"   ❌ Original image still in cache (unexpected)")
    
    # Test cache clearing
    print("\n6️⃣  Testing cache clear...")
    ocr.clear_cache()
    stats = ocr.get_cache_stats()
    
    if stats['cache_hits'] == 0 and stats['cache_misses'] == 0:
        print(f"   ✅ Cache cleared successfully")
    else:
        print(f"   ❌ Cache not fully cleared")
        return False
    
    print("\n" + "=" * 70)
    print("✅ OCR CACHE TEST PASSED")
    print("=" * 70)
    
    return True


def test_mock_cache():
    """Test cache with mock data (no API calls)"""
    print("\n🔧 Running mock cache test...")
    
    # Create a mock OCR class for testing
    class MockReceiptOCR(ReceiptOCR):
        def _ocr_api_call(self, image_hash: str, base64_image: str) -> str:
            # Return mock JSON response
            return '''{"restaurant_name": "Test Restaurant", "date": "2024-01-01", 
                      "items": [], "subtotal": 10.00, "tax": 1.00, "tip": 2.00, 
                      "total": 13.00, "confidence_score": 1.0}'''
    
    # Test with mock
    ocr = MockReceiptOCR("dummy_key", cache_size=5)
    
    test_image = TEST_PNG
    
    # First call
    result1 = ocr.process_image_bytes(test_image)
    stats1 = ocr.get_cache_stats()
    print(f"   After 1st call: Hits={stats1['cache_hits']}, Misses={stats1['cache_misses']}")
    
    # Second call (should hit cache)
    result2 = ocr.process_image_bytes(test_image)
    stats2 = ocr.get_cache_stats()
    print(f"   After 2nd call: Hits={stats2['cache_hits']}, Misses={stats2['cache_misses']}")
    
    if stats2['cache_hits'] == 1 and stats2['cache_misses'] == 1:
        print("\n✅ Mock cache test passed")
        return True
    else:
        print("\n❌ Mock cache test failed")
        return False


if __name__ == "__main__":
    success = test_ocr_cache()
    sys.exit(0 if success else 1)