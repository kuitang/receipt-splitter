#!/usr/bin/env python
"""
Test script to verify rate limiting is working correctly.
"""
import requests
import time
from typing import List, Tuple

# Test endpoint URLs (adjust port if needed)
BASE_URL = "http://localhost:8000"
TEST_ENDPOINTS = [
    ("/", "GET", 60),  # 60 requests per minute
    # Can't test POST endpoints without valid data
]

def test_rate_limit(url: str, method: str = "GET", expected_limit: int = 60) -> Tuple[bool, str]:
    """Test if rate limiting kicks in after expected number of requests"""
    
    print(f"\nTesting {method} {url} - Limit: {expected_limit}/min")
    print("-" * 50)
    
    successful = 0
    rate_limited = False
    
    # Make requests until we get rate limited
    for i in range(expected_limit + 10):
        try:
            if method == "GET":
                response = requests.get(BASE_URL + url)
            else:
                response = requests.post(BASE_URL + url)
            
            if response.status_code == 429:
                rate_limited = True
                print(f"✅ Rate limited after {successful} requests (expected ~{expected_limit})")
                break
            elif response.status_code in [200, 201, 302, 403]:  # Normal responses
                successful += 1
                if successful % 10 == 0:
                    print(f"  {successful} requests successful...")
            else:
                print(f"  Unexpected status: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Could not connect to server. Is it running on port 8000?")
            return False, "Connection failed"
        except Exception as e:
            print(f"❌ Error: {e}")
            return False, str(e)
    
    if not rate_limited:
        return False, f"Not rate limited after {successful} requests"
    
    # Test that we're still rate limited
    response = requests.get(BASE_URL + url)
    if response.status_code == 429:
        print("✅ Still rate limited on next request")
        return True, "Rate limiting working correctly"
    else:
        return False, "Rate limit not persistent"

def main():
    """Run all rate limit tests"""
    print("=" * 60)
    print("RATE LIMITING TEST SUITE")
    print("=" * 60)
    print("\n⚠️  Make sure the Django development server is running:")
    print("    cd /home/kuitang/git/receipt-splitter")
    print("    source venv/bin/activate")
    print("    python manage.py runserver")
    
    input("\nPress Enter when ready to test...")
    
    results = []
    for endpoint, method, limit in TEST_ENDPOINTS:
        passed, message = test_rate_limit(endpoint, method, limit)
        results.append((endpoint, passed, message))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for endpoint, passed, message in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {endpoint} - {message}")
    
    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All rate limiting tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check configuration.")

if __name__ == "__main__":
    main()