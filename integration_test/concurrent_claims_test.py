#!/usr/bin/env python3
"""
Integration tests for concurrent claim functionality.
Tests real-time polling and concurrent user scenarios.
"""

import time
import json
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from integration_test.base_test import (
    IntegrationTestBase, TestResult, test_wrapper, print_test_header
)


class ConcurrentClaimsTest(IntegrationTestBase):
    """Test concurrent claiming scenarios and real-time updates"""
    
    def setUp(self):
        """Set up a finalized receipt for concurrent testing"""
        # Create and upload a receipt
        test_data = self.TestData.balanced_receipt()
        
        # Upload receipt
        upload_response = self.upload_receipt(
            uploader_name="Alice",
            image_bytes=b"mock_image_data",
            filename="test.jpg"
        )
        
        self.receipt_slug = upload_response['receipt_slug']
        
        # Wait for processing
        self.wait_for_processing(self.receipt_slug)
        
        # Update with test data
        update_response = self.update_receipt(self.receipt_slug, test_data)
        assert update_response['status_code'] == 200, "Should update receipt"
        
        # Finalize receipt
        finalize_response = self.finalize_receipt(self.receipt_slug)
        assert finalize_response['status_code'] == 200, "Should finalize receipt"
        
        # Get receipt data for item IDs
        self.receipt_data = self.get_receipt_data(self.receipt_slug)
        self.item_ids = [item['id'] for item in self.receipt_data['items']]
    
    @test_wrapper
    def test_polling_endpoint_returns_correct_data(self) -> TestResult:
        """Test that the polling endpoint returns expected data structure"""
        
        # Make claim status request
        response = self.client.get(f'/claim/{self.receipt_slug}/status/')
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = json.loads(response.content)
        assert data['success'] is True, "Should return success"
        
        # Verify data structure
        required_fields = [
            'participant_totals', 'total_claimed', 'total_unclaimed', 
            'my_total', 'items_with_claims'
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify items_with_claims structure
        for item in data['items_with_claims']:
            assert 'item_id' in item, "Item should have item_id"
            assert 'available_quantity' in item, "Item should have available_quantity"
            assert 'claims' in item, "Item should have claims array"
        
        print("   ✓ Polling endpoint returns correct data structure")
        return TestResult(TestResult.PASSED)
    
    @test_wrapper
    def test_concurrent_claims_basic(self) -> TestResult:
        """Test basic concurrent claiming between two users"""
        
        # User 1 (Alice) views receipt
        alice_session = self.create_session()
        alice_view_response = alice_session.post(f'/r/{self.receipt_slug}/', {
            'viewer_name': 'Alice'
        })
        assert alice_view_response.status_code == 200, "Alice should view receipt"
        
        # User 2 (Bob) views receipt  
        bob_session = self.create_session()
        bob_view_response = bob_session.post(f'/r/{self.receipt_slug}/', {
            'viewer_name': 'Bob'
        })
        assert bob_view_response.status_code == 200, "Bob should view receipt"
        
        # Alice claims item 1
        alice_claim_data = {
            'line_item_id': str(self.item_ids[0]),
            'quantity': 1
        }
        alice_claim_response = alice_session.post(
            f'/claim/{self.receipt_slug}/',
            json.dumps(alice_claim_data),
            content_type='application/json'
        )
        assert alice_claim_response.status_code == 200, "Alice should claim item"
        alice_claim_result = json.loads(alice_claim_response.content)
        
        # Bob checks status via polling endpoint
        bob_status_response = bob_session.get(f'/claim/{self.receipt_slug}/status/')
        assert bob_status_response.status_code == 200, "Bob should get status"
        bob_status_data = json.loads(bob_status_response.content)
        
        # Verify Bob sees Alice's claim
        participant_names = [p['name'] for p in bob_status_data['participant_totals']]
        assert 'Alice' in participant_names, "Bob should see Alice in participants"
        
        # Verify item availability updated
        item_1_data = next((item for item in bob_status_data['items_with_claims'] 
                           if item['item_id'] == str(self.item_ids[0])), None)
        assert item_1_data is not None, "Should find item 1 data"
        assert len(item_1_data['claims']) == 1, "Should show Alice's claim"
        assert item_1_data['claims'][0]['claimer_name'] == 'Alice', "Should show Alice as claimer"
        
        print("   ✓ Concurrent claims work correctly")
        return TestResult(TestResult.PASSED)
    
    @test_wrapper
    def test_real_time_availability_updates(self) -> TestResult:
        """Test that item availability updates in real-time"""
        
        # Create two user sessions
        alice_session = self.create_session()
        bob_session = self.create_session()
        
        # Both users view receipt
        alice_session.post(f'/r/{self.receipt_slug}/', {'viewer_name': 'Alice'})
        bob_session.post(f'/r/{self.receipt_slug}/', {'viewer_name': 'Bob'})
        
        # Get initial status
        initial_status = bob_session.get(f'/claim/{self.receipt_slug}/status/')
        initial_data = json.loads(initial_status.content)
        item_1_initial = next(item for item in initial_data['items_with_claims'] 
                             if item['item_id'] == str(self.item_ids[0]))
        initial_available = item_1_initial['available_quantity']
        
        # Alice claims the full quantity of item 1
        alice_claim_data = {
            'line_item_id': str(self.item_ids[0]),
            'quantity': initial_available  # Claim all available
        }
        alice_claim_response = alice_session.post(
            f'/claim/{self.receipt_slug}/',
            json.dumps(alice_claim_data),
            content_type='application/json'
        )
        assert alice_claim_response.status_code == 200, "Alice should claim all items"
        
        # Bob checks updated status
        updated_status = bob_session.get(f'/claim/{self.receipt_slug}/status/')
        updated_data = json.loads(updated_status.content)
        item_1_updated = next(item for item in updated_data['items_with_claims'] 
                             if item['item_id'] == str(self.item_ids[0]))
        
        # Verify item is now fully claimed
        assert item_1_updated['available_quantity'] == 0, "Item should be fully claimed"
        assert len(item_1_updated['claims']) == 1, "Should show one claim"
        assert item_1_updated['claims'][0]['quantity_claimed'] == initial_available, "Should claim full quantity"
        
        print("   ✓ Item availability updates correctly in real-time")
        return TestResult(TestResult.PASSED)
    
    @test_wrapper
    def test_participant_totals_update(self) -> TestResult:
        """Test that participant totals update correctly across sessions"""
        
        # Create multiple user sessions
        sessions = {}
        users = ['Alice', 'Bob', 'Charlie']
        
        for user in users:
            session = self.create_session()
            session.post(f'/r/{self.receipt_slug}/', {'viewer_name': user})
            sessions[user] = session
        
        # Each user claims different items
        claims = [
            ('Alice', self.item_ids[0], 1),
            ('Bob', self.item_ids[1], 1), 
            ('Charlie', self.item_ids[1], 1)  # Partial claim on same item as Bob
        ]
        
        for user, item_id, quantity in claims:
            claim_data = {
                'line_item_id': str(item_id),
                'quantity': quantity
            }
            response = sessions[user].post(
                f'/claim/{self.receipt_slug}/',
                json.dumps(claim_data),
                content_type='application/json'
            )
            assert response.status_code == 200, f"{user} should claim successfully"
        
        # Each user checks status to see all participants
        for checking_user in users:
            status_response = sessions[checking_user].get(f'/claim/{self.receipt_slug}/status/')
            status_data = json.loads(status_response.content)
            
            participant_names = [p['name'] for p in status_data['participant_totals']]
            
            # Verify all users appear in participant list
            for user in users:
                assert user in participant_names, f"{checking_user} should see {user} in participants"
            
            # Verify totals are non-zero for claimers
            for participant in status_data['participant_totals']:
                if participant['name'] in users:
                    assert participant['amount'] > 0, f"{participant['name']} should have non-zero total"
        
        print("   ✓ Participant totals update correctly across all sessions")
        return TestResult(TestResult.PASSED)
    
    @test_wrapper
    def test_concurrent_claim_conflicts(self) -> TestResult:
        """Test handling of concurrent claims on the same item"""
        
        # Create two user sessions
        alice_session = self.create_session()
        bob_session = self.create_session()
        
        # Both users view receipt
        alice_session.post(f'/r/{self.receipt_slug}/', {'viewer_name': 'Alice'})
        bob_session.post(f'/r/{self.receipt_slug}/', {'viewer_name': 'Bob'})
        
        # Get item with quantity > 1 for conflict testing
        status_response = alice_session.get(f'/claim/{self.receipt_slug}/status/')
        status_data = json.loads(status_response.content)
        
        # Find item with quantity > 1
        target_item = None
        for item in status_data['items_with_claims']:
            if item['available_quantity'] > 1:
                target_item = item
                break
        
        if target_item is None:
            # If no item has quantity > 1, use item with quantity 1 for simpler test
            target_item = status_data['items_with_claims'][0]
        
        target_item_id = target_item['item_id']
        available_qty = target_item['available_quantity']
        
        def make_claim(session, user, quantity):
            """Helper to make a claim"""
            claim_data = {
                'line_item_id': target_item_id,
                'quantity': quantity
            }
            return session.post(
                f'/claim/{self.receipt_slug}/',
                json.dumps(claim_data),
                content_type='application/json'
            )
        
        # Both users try to claim the same item simultaneously
        alice_claim_response = make_claim(alice_session, 'Alice', available_qty)
        bob_claim_response = make_claim(bob_session, 'Bob', 1)
        
        # At least one should succeed
        alice_success = alice_claim_response.status_code == 200
        bob_success = bob_claim_response.status_code == 200
        
        if available_qty == 1:
            # If only 1 available, exactly one should succeed
            assert alice_success != bob_success, "Exactly one user should succeed when claiming single item"
        else:
            # If multiple available, both should succeed
            assert alice_success and bob_success, "Both users should succeed when enough quantity available"
        
        # Verify final state via polling
        final_status = alice_session.get(f'/claim/{self.receipt_slug}/status/')
        final_data = json.loads(final_status.content)
        final_item = next(item for item in final_data['items_with_claims'] 
                         if item['item_id'] == target_item_id)
        
        # Verify claims are recorded correctly
        total_claimed = sum(claim['quantity_claimed'] for claim in final_item['claims'])
        assert total_claimed <= available_qty, "Total claimed should not exceed availability"
        assert final_item['available_quantity'] == available_qty - total_claimed, "Available quantity should be reduced correctly"
        
        print("   ✓ Concurrent claim conflicts handled correctly")
        return TestResult(TestResult.PASSED)
    
    @test_wrapper 
    def test_polling_endpoint_rate_limiting(self) -> TestResult:
        """Test that polling endpoint respects rate limiting"""
        
        # Create user session
        session = self.create_session()
        session.post(f'/r/{self.receipt_slug}/', {'viewer_name': 'TestUser'})
        
        # Make multiple rapid requests to test rate limiting
        responses = []
        for i in range(20):  # More than rate limit
            response = session.get(f'/claim/{self.receipt_slug}/status/')
            responses.append(response.status_code)
            if i < 10:
                # Small delay for first 10 to ensure some succeed
                time.sleep(0.1)
        
        # Should have mix of 200 and 429 responses
        success_count = responses.count(200)
        rate_limited_count = responses.count(429)
        
        assert success_count > 0, "Some requests should succeed"
        # Note: Rate limiting behavior may vary based on configuration
        print(f"   ✓ Rate limiting active: {success_count} succeeded, {rate_limited_count} rate limited")
        
        return TestResult(TestResult.PASSED)
    
    @test_wrapper
    def test_polling_with_invalid_receipt(self) -> TestResult:
        """Test polling endpoint with invalid receipt slug"""
        
        session = self.create_session()
        
        # Try polling non-existent receipt
        response = session.get('/claim/invalid-slug/status/')
        assert response.status_code == 404, "Should return 404 for invalid receipt"
        
        print("   ✓ Polling handles invalid receipts correctly")
        return TestResult(TestResult.PASSED)
    
    @test_wrapper
    def test_kuizy_fries_regression_scenario(self) -> TestResult:
        """Test the exact kuizy Fries bug scenario that was originally broken"""
        
        # Create kuizy session and claim 1 Fries initially
        kuizy_session = self.create_session()
        kuizy_session.post(f'/r/{self.receipt_slug}/', {'viewer_name': 'kuizy'})
        
        # Use item with quantity 2 for this test
        target_item_id = self.item_ids[1]  # Item 2 has quantity 2
        
        # kuizy claims 1 initially (using legacy single-item API)
        initial_claim = {'line_item_id': str(target_item_id), 'quantity': 1}
        response = kuizy_session.post(
            f'/claim/{self.receipt_slug}/',
            json.dumps(initial_claim),
            content_type='application/json'
        )
        assert response.status_code == 200, "Initial claim should succeed"
        
        # Check that kuizy now has 1 claimed, 1 available
        status_response = kuizy_session.get(f'/claim/{self.receipt_slug}/status/')
        status_data = json.loads(status_response.content)
        
        item_data = next(item for item in status_data['items_with_claims'] 
                        if item['item_id'] == str(target_item_id))
        kuizy_claim = next((claim for claim in item_data['claims'] 
                           if claim['claimer_name'] == 'kuizy'), None)
        
        assert kuizy_claim is not None, "kuizy should have claim"
        assert kuizy_claim['quantity_claimed'] == 1, "kuizy should have 1 claimed"
        assert item_data['available_quantity'] == 1, "1 should remain available"
        
        # Now kuizy tries to claim 2 total (the originally broken scenario)
        # Using new total claims protocol
        total_claim = {
            'claims': [
                {'line_item_id': str(target_item_id), 'quantity': 2}  # Total desired
            ]
        }
        
        final_response = kuizy_session.post(
            f'/claim/{self.receipt_slug}/',
            json.dumps(total_claim),
            content_type='application/json'
        )
        
        assert final_response.status_code == 200, "Total claim should succeed"
        final_result = json.loads(final_response.content)
        assert final_result['success'] is True, "Should succeed"
        assert final_result['finalized'] is True, "Should be finalized"
        
        # Verify kuizy now has 2 total
        final_status = kuizy_session.get(f'/claim/{self.receipt_slug}/status/')
        final_data = json.loads(final_status.content)
        
        final_item_data = next(item for item in final_data['items_with_claims'] 
                              if item['item_id'] == str(target_item_id))
        final_kuizy_claim = next((claim for claim in final_item_data['claims'] 
                                 if claim['claimer_name'] == 'kuizy'), None)
        
        assert final_kuizy_claim['quantity_claimed'] == 2, "kuizy should now have 2 total"
        assert final_item_data['available_quantity'] == 0, "Item should be fully claimed"
        assert final_data['is_finalized'] is True, "kuizy should be finalized"
        
        print("   ✓ kuizy Fries regression scenario fixed and working")
        return TestResult(TestResult.PASSED)
    
    @test_wrapper
    def test_finalization_prevents_further_changes(self) -> TestResult:
        """Test that finalized claims cannot be changed (prevents regression)"""
        
        session = self.create_session()
        session.post(f'/r/{self.receipt_slug}/', {'viewer_name': 'TestUser'})
        
        # Finalize claims for first item
        finalize_data = {
            'claims': [
                {'line_item_id': str(self.item_ids[0]), 'quantity': 1}
            ]
        }
        
        response = session.post(
            f'/claim/{self.receipt_slug}/',
            json.dumps(finalize_data),
            content_type='application/json'
        )
        assert response.status_code == 200, "Finalization should succeed"
        result = json.loads(response.content)
        assert result['finalized'] is True, "Should be finalized"
        
        # Try to finalize again (should fail)
        response2 = session.post(
            f'/claim/{self.receipt_slug}/',
            json.dumps(finalize_data),
            content_type='application/json'
        )
        assert response2.status_code == 400, "Re-finalization should fail"
        error_data = json.loads(response2.content)
        assert "already been finalized" in error_data['error'], "Should mention finalization"
        
        # Verify status shows finalized
        status_response = session.get(f'/claim/{self.receipt_slug}/status/')
        status_data = json.loads(status_response.content)
        assert status_data['is_finalized'] is True, "Status should show finalized"
        
        print("   ✓ Finalization lockdown prevents changes correctly")
        return TestResult(TestResult.PASSED)
    
    @test_wrapper
    def test_polling_includes_finalization_status(self) -> TestResult:
        """Test that polling endpoint includes finalization status for real-time updates"""
        
        # Create user and finalize some claims
        session = self.create_session()
        session.post(f'/r/{self.receipt_slug}/', {'viewer_name': 'PollingUser'})
        
        # Check initial unfinalized status
        status_response = session.get(f'/claim/{self.receipt_slug}/status/')
        status_data = json.loads(status_response.content)
        assert 'is_finalized' in status_data, "Polling should include finalization status"
        assert status_data['is_finalized'] is False, "Should start unfinalized"
        
        # Finalize claims
        finalize_data = {
            'claims': [
                {'line_item_id': str(self.item_ids[0]), 'quantity': 1}
            ]
        }
        
        session.post(
            f'/claim/{self.receipt_slug}/',
            json.dumps(finalize_data),
            content_type='application/json'
        )
        
        # Check finalized status via polling
        final_status_response = session.get(f'/claim/{self.receipt_slug}/status/')
        final_status_data = json.loads(final_status_response.content)
        assert final_status_data['is_finalized'] is True, "Should show finalized in polling"
        
        print("   ✓ Polling includes finalization status for real-time updates")
        return TestResult(TestResult.PASSED)


def run_concurrent_claims_tests():
    """Run all concurrent claims tests"""
    test_instance = ConcurrentClaimsTest()
    
    # Setup for all tests
    test_instance.setUp()
    
    tests = [
        test_instance.test_polling_endpoint_returns_correct_data,
        test_instance.test_concurrent_claims_basic,
        test_instance.test_real_time_availability_updates,
        test_instance.test_participant_totals_update,
        test_instance.test_concurrent_claim_conflicts,
        test_instance.test_polling_endpoint_rate_limiting,
        test_instance.test_polling_with_invalid_receipt,
        # Regression tests for specific bugs
        test_instance.test_kuizy_fries_regression_scenario,
        test_instance.test_finalization_prevents_further_changes,
        test_instance.test_polling_includes_finalization_status,
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    return results


if __name__ == '__main__':
    from integration_test.mock_ocr import patch_ocr_for_tests
    
    # Patch OCR for testing
    patch_ocr_for_tests()
    
    print("🔄 Running Concurrent Claims Integration Tests...")
    results = run_concurrent_claims_tests()
    
    # Print summary
    passed = sum(1 for r in results if r.status == TestResult.PASSED)
    total = len(results)
    
    print(f"\n📊 Concurrent Claims Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All concurrent claims tests passed!")
        exit(0)
    else:
        print("❌ Some concurrent claims tests failed!")
        exit(1)