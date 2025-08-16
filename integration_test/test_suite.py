#!/usr/bin/env python3
"""
Consolidated Integration Test Suite for Receipt Splitter
Runs all integration tests with proper OCR mocking.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Tuple
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import test utilities
from integration_test.base_test import (
    IntegrationTestBase, TestDataGenerator, SecurityTestHelper,
    print_test_header, print_test_result, print_test_summary
)
from integration_test.mock_ocr import patch_ocr_for_tests, get_ocr_status


class ReceiptWorkflowTest(IntegrationTestBase):
    """Test complete receipt workflow: upload, edit, finalize, claim"""
    
    def test_complete_workflow(self) -> bool:
        """Test the entire receipt workflow end-to-end"""
        print_test_header("Complete Receipt Workflow Test")
        
        try:
            # Step 1: Upload receipt
            print("\n📤 Step 1: Upload Receipt")
            upload_response = self.upload_receipt(
                uploader_name="Test User Alice",
                image_bytes=self.create_test_image(1000)  # Triggers default mock data
            )
            
            assert upload_response['status_code'] == 302, "Upload should redirect"
            receipt_slug = upload_response['receipt_slug']
            assert receipt_slug is not None, "Should extract receipt slug from redirect"
            print(f"   ✓ Receipt uploaded, slug: {receipt_slug}")
            
            # Step 2: Wait for processing
            print("\n⏳ Step 2: Wait for Processing")
            assert self.wait_for_processing(receipt_slug), "Processing should complete"
            print("   ✓ Receipt processed successfully")
            
            # Step 3: Get receipt data
            print("\n📊 Step 3: Verify OCR Data")
            receipt_data = self.get_receipt_data(receipt_slug)
            assert receipt_data is not None, "Should get receipt data"
            assert receipt_data['restaurant_name'] == "Test Restaurant", "Restaurant name should match mock"
            assert len(receipt_data['items']) == 3, "Should have 3 items from mock"
            print(f"   ✓ OCR extracted {len(receipt_data['items'])} items")
            print(f"   ✓ Restaurant: {receipt_data['restaurant_name']}")
            
            # Step 4: Edit receipt - try invalid data first
            print("\n✏️ Step 4: Edit Receipt")
            print("   Testing invalid data...")
            invalid_data = TestDataGenerator.unbalanced_receipt()
            update_response = self.update_receipt(receipt_slug, invalid_data)
            assert update_response['status_code'] == 200, "Update should succeed"
            assert update_response['data']['is_balanced'] == False, "Should detect unbalanced receipt"
            print("   ✓ Validation correctly detected unbalanced receipt")
            
            # Step 5: Fix and save valid data
            print("   Saving valid data...")
            valid_data = TestDataGenerator.balanced_receipt()
            update_response = self.update_receipt(receipt_slug, valid_data)
            assert update_response['status_code'] == 200, "Update should succeed"
            assert update_response['data']['is_balanced'] == True, "Should be balanced"
            print("   ✓ Receipt updated with balanced data")
            
            # Step 6: Try to finalize unbalanced receipt (should fail)
            print("\n🔒 Step 5: Test Finalization")
            print("   Testing finalization of unbalanced receipt...")
            self.update_receipt(receipt_slug, invalid_data)
            finalize_response = self.finalize_receipt(receipt_slug)
            assert finalize_response['status_code'] == 400, "Should not finalize unbalanced receipt"
            print("   ✓ Correctly prevented finalizing unbalanced receipt")
            
            # Step 7: Finalize with valid data
            print("   Finalizing balanced receipt...")
            self.update_receipt(receipt_slug, valid_data)
            finalize_response = self.finalize_receipt(receipt_slug)
            assert finalize_response['status_code'] == 200, "Should finalize balanced receipt"
            share_url = finalize_response['data']['share_url']
            print(f"   ✓ Receipt finalized, share URL: {share_url}")
            
            # Step 8: New session - claim items as different users
            print("\n👥 Step 6: Test Item Claims")
            
            # User B claims first item
            print("   User B claiming items...")
            user_b = self.create_new_session()
            assert user_b.set_viewer_name(receipt_slug, "Test User Bob"), "Should set viewer name"
            
            receipt_data = user_b.get_receipt_data(receipt_slug)
            first_item_id = receipt_data['items'][0]['id']
            claim_response = user_b.claim_item(receipt_slug, first_item_id, quantity=1)
            assert claim_response['status_code'] == 200, "Should claim item"
            print("   ✓ User B claimed first item")
            
            # User C claims second item
            print("   User C claiming items...")
            user_c = self.create_new_session()
            assert user_c.set_viewer_name(receipt_slug, "Test User Carol"), "Should set viewer name"
            
            second_item_id = receipt_data['items'][1]['id']
            claim_response = user_c.claim_item(receipt_slug, second_item_id, quantity=2)
            assert claim_response['status_code'] == 200, "Should claim item"
            print("   ✓ User C claimed second item")
            
            # Step 9: Verify totals
            print("\n💰 Step 7: Verify Totals")
            final_data = self.get_receipt_data(receipt_slug)
            
            # Calculate claimed totals
            total_claimed = Decimal('0')
            claims_by_user = {}
            
            for item in final_data['items']:
                for claim in item.get('claims', []):
                    user = claim['claimer_name']
                    amount = Decimal(str(claim['share_amount']))
                    claims_by_user[user] = claims_by_user.get(user, Decimal('0')) + amount
                    total_claimed += amount
            
            print(f"   Claims by user:")
            for user, amount in claims_by_user.items():
                print(f"     - {user}: ${amount:.2f}")
            
            receipt_total = Decimal(str(final_data['total']))
            unclaimed = receipt_total - total_claimed
            print(f"   Total claimed: ${total_claimed:.2f}")
            print(f"   Total unclaimed: ${unclaimed:.2f}")
            print(f"   Receipt total: ${receipt_total:.2f}")
            
            # Step 10: Test unclaim
            print("\n🔄 Step 8: Test Unclaim")
            if final_data['items'][0].get('claims'):
                claim_id = final_data['items'][0]['claims'][0]['id']
                unclaim_response = user_b.unclaim_item(receipt_slug, claim_id)
                assert unclaim_response['status_code'] == 200, "Should unclaim item"
                print("   ✓ User B successfully unclaimed item")
            
            print("\n✅ Complete workflow test PASSED")
            return True
            
        except AssertionError as e:
            print(f"\n❌ Workflow test failed: {e}")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False


class SecurityValidationTest(IntegrationTestBase):
    """Security validation tests based on SECURITY_AUDIT_REPORT.md"""
    
    def test_input_validation(self) -> bool:
        """Test input validation against XSS and SQL injection"""
        print_test_header("Security: Input Validation Test")
        
        try:
            # Test XSS in uploader name
            print("\n🛡️ Testing XSS Prevention")
            xss_payloads = SecurityTestHelper.get_xss_payloads()
            
            for i, payload in enumerate(xss_payloads[:3]):  # Test first 3 payloads
                response = self.upload_receipt(
                    uploader_name=payload,
                    image_bytes=self.create_test_image(50)
                )
                
                # Should either reject or sanitize
                if response['status_code'] == 302:
                    # If accepted, verify it's sanitized when displayed
                    receipt_slug = response['receipt_slug']
                    data = self.get_receipt_data(receipt_slug)
                    assert '<script>' not in data.get('uploader_name', ''), \
                        f"XSS not sanitized: {data.get('uploader_name')}"
                    print(f"   ✓ XSS payload {i+1} sanitized")
                else:
                    print(f"   ✓ XSS payload {i+1} rejected")
            
            # Test SQL injection in restaurant name
            print("\n🛡️ Testing SQL Injection Prevention")
            upload_response = self.upload_receipt("Test Security User")
            receipt_slug = upload_response['receipt_slug']
            self.wait_for_processing(receipt_slug)
            
            sql_payloads = SecurityTestHelper.get_sql_injection_payloads()
            for i, payload in enumerate(sql_payloads[:3]):  # Test first 3 payloads
                data = TestDataGenerator.balanced_receipt()
                data['restaurant_name'] = payload
                
                response = self.update_receipt(receipt_slug, data)
                # Should either reject or safely handle
                assert response['status_code'] in [200, 400], \
                    "Should handle SQL injection attempt"
                print(f"   ✓ SQL injection payload {i+1} handled safely")
            
            print("\n✅ Input validation test PASSED")
            return True
            
        except AssertionError as e:
            print(f"\n❌ Security test failed: {e}")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False
    
    def test_file_upload_security(self) -> bool:
        """Test file upload size limits and validation"""
        print_test_header("Security: File Upload Test")
        
        try:
            # Test oversized file
            print("\n📁 Testing File Size Limits")
            oversized = SecurityTestHelper.get_oversized_data(11)  # 11MB
            response = self.upload_receipt(
                uploader_name="Test File Security",
                image_bytes=oversized
            )
            
            assert response['status_code'] != 302, "Should reject oversized file"
            print("   ✓ Oversized file (11MB) rejected")
            
            # Test empty file
            print("\n📁 Testing Empty File")
            response = self.upload_receipt(
                uploader_name="Test Empty File",
                image_bytes=b''
            )
            assert response['status_code'] != 302, "Should reject empty file"
            print("   ✓ Empty file rejected")
            
            print("\n✅ File upload security test PASSED")
            return True
            
        except AssertionError as e:
            print(f"\n❌ File security test failed: {e}")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False
    
    def test_session_security(self) -> bool:
        """Test session isolation and access control"""
        print_test_header("Security: Session Isolation Test")
        
        try:
            # User A uploads receipt
            print("\n🔐 Testing Session Isolation")
            user_a = self.create_new_session()
            upload_response = user_a.upload_receipt("User A")
            receipt_slug = upload_response['receipt_slug']
            user_a.wait_for_processing(receipt_slug)
            
            # User B tries to edit User A's receipt
            print("   Testing unauthorized edit attempt...")
            user_b = self.create_new_session()
            data = TestDataGenerator.balanced_receipt()
            response = user_b.update_receipt(receipt_slug, data)
            
            assert response['status_code'] == 403, \
                "Should prevent unauthorized edit"
            print("   ✓ Unauthorized edit prevented")
            
            # User B tries to finalize User A's receipt
            print("   Testing unauthorized finalize attempt...")
            response = user_b.finalize_receipt(receipt_slug)
            assert response['status_code'] == 403, \
                "Should prevent unauthorized finalize"
            print("   ✓ Unauthorized finalize prevented")
            
            # User A can still edit their own receipt
            print("   Testing authorized edit...")
            response = user_a.update_receipt(receipt_slug, data)
            assert response['status_code'] == 200, \
                "Owner should be able to edit"
            print("   ✓ Authorized edit allowed")
            
            print("\n✅ Session security test PASSED")
            return True
            
        except AssertionError as e:
            print(f"\n❌ Session security test failed: {e}")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False


class ValidationTest(IntegrationTestBase):
    """Test receipt validation logic"""
    
    def test_balance_validation(self) -> bool:
        """Test receipt balance validation"""
        print_test_header("Receipt Balance Validation Test")
        
        try:
            # Upload receipt
            print("\n💰 Setting up test receipt")
            response = self.upload_receipt("Test Validation User")
            receipt_slug = response['receipt_slug']
            self.wait_for_processing(receipt_slug)
            
            # Test various validation scenarios
            test_cases = [
                ("Balanced receipt", TestDataGenerator.balanced_receipt(), True),
                ("Unbalanced total", TestDataGenerator.unbalanced_receipt(), False),
                ("Negative tip (discount)", TestDataGenerator.receipt_with_negative_tip(), True),
            ]
            
            for name, data, should_balance in test_cases:
                print(f"\n   Testing: {name}")
                response = self.update_receipt(receipt_slug, data)
                assert response['status_code'] == 200, "Update should succeed"
                
                is_balanced = response['data']['is_balanced']
                if should_balance:
                    assert is_balanced == True, f"{name} should be balanced"
                    print(f"   ✓ {name} correctly validated as balanced")
                else:
                    assert is_balanced == False, f"{name} should be unbalanced"
                    print(f"   ✓ {name} correctly validated as unbalanced")
            
            print("\n✅ Balance validation test PASSED")
            return True
            
        except AssertionError as e:
            print(f"\n❌ Validation test failed: {e}")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False


class PerformanceTest(IntegrationTestBase):
    """Test application performance with large data"""
    
    def test_large_receipt(self) -> bool:
        """Test handling of receipts with many items"""
        print_test_header("Performance: Large Receipt Test")
        
        try:
            # Upload and process receipt
            print("\n📊 Testing large receipt (50 items)")
            response = self.upload_receipt("Test Performance User")
            receipt_slug = response['receipt_slug']
            self.wait_for_processing(receipt_slug)
            
            # Update with many items
            large_data = TestDataGenerator.large_receipt(50)
            start_time = time.time()
            response = self.update_receipt(receipt_slug, large_data)
            update_time = time.time() - start_time
            
            assert response['status_code'] == 200, "Should handle large receipt"
            assert update_time < 5, f"Update took too long: {update_time:.2f}s"
            print(f"   ✓ Updated 50 items in {update_time:.2f}s")
            
            # Verify data integrity
            receipt_data = self.get_receipt_data(receipt_slug)
            assert len(receipt_data['items']) == 50, "Should have all 50 items"
            self.assert_receipt_balanced(receipt_data)
            print("   ✓ All items saved correctly and totals balanced")
            
            # Test claiming performance
            print("\n   Testing claim performance...")
            start_time = time.time()
            self.set_viewer_name(receipt_slug, "Performance Tester")
            
            # Claim first 10 items
            for i in range(10):
                item_id = receipt_data['items'][i]['id']
                self.claim_item(receipt_slug, item_id, quantity=1)
            
            claim_time = time.time() - start_time
            assert claim_time < 10, f"Claims took too long: {claim_time:.2f}s"
            print(f"   ✓ Claimed 10 items in {claim_time:.2f}s")
            
            print("\n✅ Performance test PASSED")
            return True
            
        except AssertionError as e:
            print(f"\n❌ Performance test failed: {e}")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "=" * 70)
    print("🧪 RECEIPT SPLITTER INTEGRATION TEST SUITE")
    print("=" * 70)
    
    # Show OCR mock status
    ocr_status = get_ocr_status()
    print(f"\n📋 OCR Configuration:")
    print(f"   Status: {ocr_status['status_message']}")
    print(f"   Environment Variable: {ocr_status['env_var']}={ocr_status['env_value']}")
    
    if ocr_status['using_real_ocr']:
        print("   ⚠️  WARNING: Using real OpenAI API - this will cost money!")
        response = input("   Continue? (y/n): ")
        if response.lower() != 'y':
            print("   Test aborted.")
            return
    
    # Apply OCR patches
    patches = patch_ocr_for_tests()
    for patch in patches:
        patch.start()
    
    try:
        # Initialize test classes
        workflow_test = ReceiptWorkflowTest()
        security_test = SecurityValidationTest()
        validation_test = ValidationTest()
        performance_test = PerformanceTest()
        
        # Run tests
        results = []
        
        # Core workflow tests
        results.append(("Complete Workflow", workflow_test.test_complete_workflow()))
        
        # Security tests
        results.append(("Input Validation Security", security_test.test_input_validation()))
        results.append(("File Upload Security", security_test.test_file_upload_security()))
        results.append(("Session Security", security_test.test_session_security()))
        
        # Validation tests
        results.append(("Balance Validation", validation_test.test_balance_validation()))
        
        # Performance tests
        results.append(("Large Receipt Performance", performance_test.test_large_receipt()))
        
        # Print summary
        print_test_summary(results)
        
        # Cleanup test data
        print("\n🧹 Cleaning up test data...")
        base_test = IntegrationTestBase()
        count = base_test.cleanup_test_receipts()
        print(f"   Deleted {count} test receipt(s)")
        
        # Return exit code
        all_passed = all(result for _, result in results)
        return 0 if all_passed else 1
        
    finally:
        # Stop patches
        for patch in patches:
            patch.stop()


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)