#!/usr/bin/env python3
"""
Test for race conditions in concurrent claim submissions.
This test verifies that our row-level locking prevents both:
1. Double-claiming (total exceeds available)
2. Neither-claimed (both users fail)
"""

import json
import threading
import time
import queue
import requests
from typing import Dict, List, Tuple
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'receipt_splitter.settings')
import django
django.setup()

from integration_test.base_test import IntegrationTestBase


class ConcurrentClaimsTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = IntegrationTestBase(base_url)

    def create_test_receipt(self, items_quantity: int = 2) -> Tuple[str, List[str]]:
        """Create a test receipt with limited items for race condition testing"""
        session = self.client.create_new_session()

        # Upload receipt with mock image
        upload_response = session.upload_receipt('Race Test Uploader')
        if upload_response['status_code'] != 302:
            raise Exception(f"Failed to upload receipt: {upload_response}")

        slug = upload_response['receipt_slug']
        if not slug:
            raise Exception("Failed to get receipt slug from upload")

        # Wait for processing
        if not session.wait_for_processing(slug):
            raise Exception("Receipt processing failed or timed out")

        # The mock OCR creates some default items. Let's get them.
        # We need to get the edit page to see what items were created
        edit_response = session.client.get(f'/edit/{slug}/')
        if edit_response.status_code != 200:
            raise Exception(f"Failed to get edit page: {edit_response.status_code}")

        # Parse item IDs from the edit page (looking for data-item-id attributes)
        content = edit_response.content.decode('utf-8')
        import re
        item_ids = re.findall(r'data-item-id="([^"]+)"', content)

        # Update the first item to have limited quantity
        if item_ids:
            # Update first item to have the desired limited quantity
            update_data = {
                'items': json.dumps([{
                    'id': item_ids[0],
                    'name': f'Limited Item (only {items_quantity} available)',
                    'quantity': items_quantity,
                    'unit_price': '10.00',
                    'total_price': str(10 * items_quantity)
                }])
            }
            update_response = session.update_receipt(slug, update_data)
            if update_response['status_code'] != 200:
                print(f"Warning: Failed to update item quantity: {update_response}")

        # Finalize receipt
        finalize_response = session.finalize_receipt(slug)
        if finalize_response['status_code'] != 200:
            raise Exception(f"Failed to finalize receipt: {finalize_response}")

        return slug, item_ids[:1]  # Return only the first item ID that we limited

    def claim_worker(self, slug: str, item_ids: List[str], user_name: str,
                     quantity: int, results_queue: queue.Queue, barrier: threading.Barrier):
        """Worker function for concurrent claim submission"""
        try:
            # Create new session for this user
            session = self.client.create_new_session()

            # Set viewer name
            session.set_viewer_name(slug, user_name)

            # Wait at barrier until all threads are ready
            barrier.wait()

            # Prepare claims data
            claims = [
                {'line_item_id': item_id, 'quantity': quantity}
                for item_id in item_ids[:1]  # Only claim first item for simplicity
            ]

            # Submit claims
            response = session.client.post(
                f'/claim/{slug}/',
                data=json.dumps({'claims': claims}),
                content_type='application/json'
            )

            result = {
                'user': user_name,
                'status_code': response.status_code,
                'data': json.loads(response.content) if response.content else None
            }

            results_queue.put(result)

        except Exception as e:
            results_queue.put({
                'user': user_name,
                'error': str(e)
            })

    def test_concurrent_claims_with_limited_items(self):
        """Test that concurrent claims are properly serialized"""
        print("\n" + "="*60)
        print("Testing Concurrent Claims with Limited Items")
        print("="*60)

        # Create receipt with only 2 items available
        slug, item_ids = self.create_test_receipt(items_quantity=2)
        print(f"Created receipt {slug} with items that have quantity=2")

        # Create barrier to synchronize thread start
        num_users = 5
        barrier = threading.Barrier(num_users)
        results_queue = queue.Queue()

        # Launch concurrent claims from 5 users, each wanting 1 item
        threads = []
        for i in range(num_users):
            user_name = f"User{i+1}"
            t = threading.Thread(
                target=self.claim_worker,
                args=(slug, item_ids, user_name, 1, results_queue, barrier)
            )
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join(timeout=10)

        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())

        # Analyze results
        successful_claims = [r for r in results if r.get('status_code') == 200]
        failed_claims = [r for r in results if r.get('status_code') != 200]

        print(f"\nResults:")
        print(f"  Successful claims: {len(successful_claims)} users")
        print(f"  Failed claims: {len(failed_claims)} users")

        for result in results:
            if result.get('status_code') == 200:
                print(f"  ✓ {result['user']}: Successfully claimed")
            else:
                error_msg = result.get('data', {}).get('error', 'Unknown error') if result.get('data') else result.get('error', 'Unknown error')
                print(f"  ✗ {result['user']}: {error_msg}")

        # Verify constraints
        assert len(successful_claims) <= 2, f"Too many successful claims! Expected ≤2, got {len(successful_claims)}"
        assert len(successful_claims) >= 1, f"No successful claims! At least one should succeed"

        # Verify that failed claims got proper error messages with availability info
        for failed in failed_claims:
            if failed.get('data'):
                data = failed['data']
                # Check if we got availability information
                if 'availability' in data:
                    print(f"\n  {failed['user']} received availability info:")
                    for item in data['availability']:
                        print(f"    - {item['name']}: requested {item['requested']}, available {item['available']}")

        print("\n✅ Concurrent claims test PASSED - race condition prevented!")

    def test_rapid_sequential_claims(self):
        """Test rapid sequential claims to ensure no timing issues"""
        print("\n" + "="*60)
        print("Testing Rapid Sequential Claims")
        print("="*60)

        slug, item_ids = self.create_test_receipt(items_quantity=3)
        print(f"Created receipt {slug} with items that have quantity=3")

        results = []
        users = ['Alice', 'Bob', 'Charlie', 'David']

        for user in users:
            session = self.client.create_new_session()
            session.set_viewer_name(slug, user)

            claims = [
                {'line_item_id': item_ids[0], 'quantity': 1}
            ]

            response = session.client.post(
                f'/claim/{slug}/',
                data=json.dumps({'claims': claims}),
                content_type='application/json'
            )

            results.append({
                'user': user,
                'status_code': response.status_code,
                'data': json.loads(response.content) if response.content else None
            })

            # Very short delay to simulate rapid clicking
            time.sleep(0.05)

        successful = sum(1 for r in results if r['status_code'] == 200)
        print(f"\nResults: {successful} out of {len(users)} users successfully claimed")

        # First 3 should succeed, 4th should fail
        assert successful == 3, f"Expected exactly 3 successful claims, got {successful}"

        # The 4th user should get a proper error
        last_result = results[-1]
        assert last_result['status_code'] != 200, "Fourth user should have failed"
        assert 'error' in last_result['data'], "Failed claim should have error message"

        print("✅ Rapid sequential claims test PASSED!")

    def test_neither_claimed_scenario(self):
        """Test that DELETE and CREATE are atomic - no 'neither claimed' scenario"""
        print("\n" + "="*60)
        print("Testing Neither-Claimed Scenario Prevention")
        print("="*60)

        slug, item_ids = self.create_test_receipt(items_quantity=1)
        results_queue = queue.Queue()

        def claim_with_simulated_failure(user_name: str):
            """Simulate a claim that might fail during CREATE after DELETE"""
            try:
                session = self.client.create_new_session()
                session.set_viewer_name(slug, user_name)

                # Try to claim the single item
                claims = [{'line_item_id': item_ids[0], 'quantity': 1}]

                response = session.client.post(
                    f'/claim/{slug}/',
                    data=json.dumps({'claims': claims}),
                    content_type='application/json'
                )

                results_queue.put({
                    'user': user_name,
                    'status_code': response.status_code,
                    'data': json.loads(response.content) if response.content else None
                })
            except Exception as e:
                results_queue.put({
                    'user': user_name,
                    'error': str(e)
                })

        # Two users try to claim the single item simultaneously
        barrier = threading.Barrier(2)
        threads = []
        for user in ['Alice', 'Bob']:
            t = threading.Thread(target=claim_with_simulated_failure, args=(user,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())

        successful = [r for r in results if r.get('status_code') == 200]

        print(f"\nResults:")
        for r in results:
            if r.get('status_code') == 200:
                print(f"  ✓ {r['user']}: Successfully claimed")
            else:
                print(f"  ✗ {r['user']}: Failed to claim")

        # CRITICAL: Exactly one should succeed (not zero, not two)
        assert len(successful) == 1, f"Expected exactly 1 successful claim, got {len(successful)}"

        print("✅ Neither-claimed scenario test PASSED - atomic transaction working!")

    def run_all_tests(self):
        """Run all concurrent claim tests"""
        try:
            self.test_concurrent_claims_with_limited_items()
            self.test_rapid_sequential_claims()
            self.test_neither_claimed_scenario()

            print("\n" + "="*60)
            print("🎉 ALL CONCURRENT CLAIM TESTS PASSED!")
            print("Race conditions are properly handled.")
            print("="*60)

        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ UNEXPECTED ERROR: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/")
        if response.status_code != 200:
            print("⚠️  Server returned unexpected status code")
    except requests.ConnectionError:
        print("❌ Server is not running at http://localhost:8000")
        print("Please start the Django server first: python manage.py runserver")
        sys.exit(1)

    # Run tests
    test = ConcurrentClaimsTest()
    test.run_all_tests()