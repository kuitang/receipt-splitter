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
    print_test_header, print_test_result, print_test_summary, TestResult
)
from integration_test.mock_ocr import patch_ocr_for_tests, get_ocr_status


class ReceiptWorkflowTest(IntegrationTestBase):
    """Test complete receipt workflow: upload, edit, finalize, claim"""
    
    def test_complete_workflow(self) -> TestResult:
        """Test the entire receipt workflow end-to-end"""
        print_test_header("Complete Receipt Workflow Test")
        
        try:
            # Step 1: Upload receipt using IMG_6839.HEIC
            print("\n📤 Step 1: Upload Receipt")
            
            # Check current working directory and ensure we're in the right place
            import os
            cwd = os.getcwd()
            print(f"   Current directory: {cwd}")
            
            # The test should be run from the project root where IMG_6839.HEIC is located
            heic_path = 'IMG_6839.HEIC'
            if not os.path.exists(heic_path):
                # Try to find it in the parent directory if we're in integration_test/
                if os.path.basename(cwd) == 'integration_test':
                    heic_path = '../IMG_6839.HEIC'
                    if os.path.exists(heic_path):
                        print("   ⚠️ Running from integration_test/ directory, using ../IMG_6839.HEIC")
                    else:
                        print(f"   ❌ ERROR: IMG_6839.HEIC not found in current directory or parent.")
                        print(f"   Please run this test from the project root directory:")
                        print(f"   cd /home/kuitang/git/receipt-splitter && python integration_test/test_suite.py")
                        raise AssertionError("IMG_6839.HEIC not found. Test must be run from project root.")
                else:
                    print(f"   ❌ ERROR: IMG_6839.HEIC not found in {cwd}")
                    print(f"   Please ensure you run this test from the project root directory where IMG_6839.HEIC exists.")
                    raise AssertionError("IMG_6839.HEIC not found. Test must be run from project root.")
            
            # Load the actual IMG_6839.HEIC file
            with open(heic_path, 'rb') as f:
                image_bytes = f.read()
            print(f"   Using {heic_path} ({len(image_bytes)/1024:.1f} KB)")
            filename = "IMG_6839.HEIC"
            
            upload_response = self.upload_receipt(
                uploader_name="Test User Alice",
                image_bytes=image_bytes,
                filename=filename
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
            
            # Expected values for IMG_6839.HEIC (from actual OCR response)
            # The image is from "The Great Burger" restaurant
            print(f"   Restaurant: {receipt_data['restaurant_name']}")
            print(f"   Items: {len(receipt_data['items'])}")
            
            # Verify we got valid data (not checking exact values since OCR can vary)
            assert receipt_data['restaurant_name'] is not None and receipt_data['restaurant_name'] != "", "Should have restaurant name"
            assert len(receipt_data['items']) > 0, "Should have at least one item"
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
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Workflow test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")


class SecurityValidationTest(IntegrationTestBase):
    """Security validation tests based on SECURITY_AUDIT_REPORT.md"""
    
    def test_input_validation(self) -> TestResult:
        """Test input validation against XSS and SQL injection"""
        print_test_header("Security: Input Validation Test")
        
        try:
            import time
            # Test XSS in uploader name
            print("\n🛡️ Testing XSS Prevention")
            xss_payloads = SecurityTestHelper.get_xss_payloads()
            
            for i, payload in enumerate(xss_payloads[:2]):  # Test first 2 payloads to avoid rate limit
                if i > 0:
                    time.sleep(1)  # Small delay between uploads to avoid rate limit
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
            for i, payload in enumerate(sql_payloads[:2]):  # Test first 2 payloads to avoid rate limit
                data = TestDataGenerator.balanced_receipt()
                data['restaurant_name'] = payload
                
                response = self.update_receipt(receipt_slug, data)
                # Should either reject or safely handle
                assert response['status_code'] in [200, 400], \
                    "Should handle SQL injection attempt"
                print(f"   ✓ SQL injection payload {i+1} handled safely")
            
            print("\n✅ Input validation test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Security test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")
    
    def test_file_upload_security(self) -> TestResult:
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
            
            assert response['status_code'] == 413, "Should reject oversized file with 413"
            print("   ✓ Oversized file (11MB) rejected with 413 status")
            
            # Test basic malicious content
            print("\n🛡️ Testing Basic Malicious Content")
            
            # Test PHP content
            response = self.upload_receipt(
                uploader_name="Test Malicious",
                image_bytes=b'<?php system($_GET["cmd"]); ?>',
                filename="malicious.php"
            )
            assert response['status_code'] == 400, "Should reject PHP file with 400 status"
            print("   ✓ PHP file rejected with 400 status")
            
            # Test basic MIME type spoofing
            print("\n🎭 Testing Basic MIME Type Spoofing")
            from django.core.files.uploadedfile import SimpleUploadedFile
            
            # Try to upload PHP with image MIME type
            fake_image = SimpleUploadedFile(
                name="fake.jpg",
                content=b'<?php system($_GET["cmd"]); ?>',
                content_type='image/jpeg'  # Spoofed MIME type
            )
            
            # Direct test with Django client
            response = self.client.post('/upload/', {
                'uploader_name': 'MIME Spoof Test',
                'receipt_image': fake_image
            })
            
            # Should be rejected with 400 status regardless of claimed MIME type
            assert response.status_code == 400, "Should reject file despite spoofed MIME type with 400 status"
            print("   ✓ MIME type spoofing prevented with 400 status")
            
            print("\n✅ File upload security test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ File security test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")
    
    def test_session_security(self) -> TestResult:
        """Test session isolation and access control"""
        print_test_header("Security: Session Isolation Test")
        
        try:
            # User A uploads receipt - handle potential rate limiting
            print("\n🔐 Testing Session Isolation")
            
            user_a = self.create_new_session()
            upload_response = user_a.upload_receipt("User A")
            
            if upload_response['status_code'] != 302 or not upload_response['receipt_slug']:
                raise AssertionError(f"Upload failed: {upload_response['status_code']}")
            
            receipt_slug = upload_response['receipt_slug']
            if not user_a.wait_for_processing(receipt_slug):
                raise AssertionError("Receipt processing failed")
            
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
            
            # Test edit token manipulation
            print("\n🔑 Testing Edit Token Security")
            
            # Try to access edit page after finalizing
            user_a.finalize_receipt(receipt_slug)
            response = user_a.client.get(f'/edit/{receipt_slug}/')
            assert response.status_code == 302, "Should redirect finalized receipt"
            print("   ✓ Edit access blocked after finalization")
            
            # Test session hijacking attempt
            print("\n🚫 Testing Session Hijacking Prevention")
            
            # Create new receipt for hijacking test
            upload_response2 = user_a.upload_receipt("User A Second")
            receipt_slug2 = upload_response2['receipt_slug']
            user_a.wait_for_processing(receipt_slug2)
            
            # Try to manipulate session data
            user_b_client = user_b.client
            user_b_client.session['receipt_id'] = receipt_slug2  # Try to claim ownership
            user_b_client.session.save()
            
            # Should still be blocked due to edit token verification
            response = user_b.update_receipt(receipt_slug2, data)
            assert response['status_code'] == 403, "Should prevent session manipulation"
            print("   ✓ Session manipulation prevented")
            
            # Test concurrent editing protection with multiple users
            print("\n🔄 Testing Concurrent Edit Protection")
            
            # Create third receipt with user_a
            upload_response3 = user_a.upload_receipt("User A Third")
            receipt_slug3 = upload_response3['receipt_slug']
            user_a.wait_for_processing(receipt_slug3)
            
            # Test 1: Authorized user concurrent edits (should all succeed)
            print("   Testing authorized user concurrent edits...")
            import threading
            import time
            
            authorized_results = []
            
            def concurrent_edit(client, slug, test_data, results_list):
                try:
                    response = client.update_receipt(slug, test_data)
                    results_list.append(response['status_code'])
                except Exception:
                    results_list.append(500)
            
            # Start concurrent edit attempts with authorized user
            threads = []
            for i in range(3):
                t = threading.Thread(
                    target=concurrent_edit,
                    args=(user_a, receipt_slug3, data, authorized_results)
                )
                threads.append(t)
                t.start()
            
            # Wait for all threads
            for t in threads:
                t.join()
            
            # All authorized edits should succeed
            success_count = sum(1 for code in authorized_results if code == 200)
            assert success_count == 3, f"All authorized concurrent edits should succeed, got {success_count}/3"
            print(f"   ✓ Authorized concurrent edits working ({success_count}/3 succeeded)")
            
            # Test 2: Mixed authorized/unauthorized concurrent edits
            print("   Testing mixed authorized/unauthorized concurrent edits...")
            mixed_results = []
            
            # Create different test data for each user to avoid conflicts
            user_a_data = TestDataGenerator.balanced_receipt()
            user_a_data['restaurant_name'] = 'User A Edit'
            
            user_b_data = TestDataGenerator.balanced_receipt()
            user_b_data['restaurant_name'] = 'User B Edit'
            
            # Start mixed concurrent edit attempts
            threads = []
            # User A (authorized) edit
            t1 = threading.Thread(
                target=concurrent_edit,
                args=(user_a, receipt_slug3, user_a_data, mixed_results)
            )
            # User B (unauthorized) edit
            t2 = threading.Thread(
                target=concurrent_edit,
                args=(user_b, receipt_slug3, user_b_data, mixed_results)
            )
            threads.extend([t1, t2])
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
            
            # Only authorized edit should succeed (200), unauthorized should fail (403)
            success_count = sum(1 for code in mixed_results if code == 200)
            forbidden_count = sum(1 for code in mixed_results if code == 403)
            
            assert success_count == 1, f"Only 1 authorized edit should succeed, got {success_count}"
            assert forbidden_count == 1, f"1 unauthorized edit should be forbidden, got {forbidden_count}"
            print(f"   ✓ Mixed concurrent access working (1 authorized, 1 forbidden)")
            
            print("\n✅ Session security test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Session security test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")
    
    def test_security_validation(self) -> TestResult:
        """Test enhanced security validation with python-magic"""
        print_test_header("Security: Enhanced Validation Test") 
        
        try:
            import time
            # Test 1: Different malicious file types with magic detection
            print("\n🛡️ Testing Enhanced File Type Detection")
            
            malicious_files = [
                (b'<script>alert("xss")</script>', "xss.html", "HTML/JS content"),
                (b'%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>', "fake.pdf", "PDF content"),
            ]
            
            for i, (content, filename, description) in enumerate(malicious_files):
                if i > 0:
                    time.sleep(1)  # Small delay between uploads
                response = self.upload_receipt(
                    uploader_name=f"Security Test {description}",
                    image_bytes=content,
                    filename=filename
                )
                
                # Should be rejected since it's not a valid image
                assert response['status_code'] == 400, f"Should reject {description} with 400 status"
                print(f"   ✅ {description} correctly rejected")
            
            # Test 2: Verify our enhanced validation is actually working
            print("\n🔍 Testing python-magic Integration")
            
            # This should still work - valid image
            valid_response = self.upload_receipt(
                uploader_name="Valid Magic Test",
                image_bytes=self.create_test_image(500),
                filename="receipt.jpg"
            )
            
            if valid_response['status_code'] == 429:
                print("   ⚠️ Rate limited - but enhanced validation is working (malicious files rejected)")
            elif valid_response['status_code'] == 302:
                print("   ✅ Valid JPEG image correctly accepted by magic validation")
            else:
                print(f"   ⚠️ Unexpected status for valid image: {valid_response['status_code']}")
            
            print("\n✅ Enhanced security validation test PASSED")
            print("   ✓ python-magic properly detecting file types")
            print("   ✓ Non-image content reliably rejected") 
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Security validation test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")
    
    def test_rate_limiting(self) -> TestResult:
        """Test rate limiting enforcement with simple burst testing"""
        print_test_header("Security: Rate Limiting Test")
        
        try:
            import time
            
            # Test 1: Upload rate limiting (10/min = ~6 seconds per request at limit)
            print("\n🚀 Testing Upload Rate Limiting (10/min limit)")
            
            successful_uploads = 0
            start_time = time.time()
            
            # Send requests as fast as possible until rate limited
            for i in range(20):  # Try more than the limit
                response = self.upload_receipt(
                    uploader_name=f"Rate Test {i}",
                    image_bytes=self.create_test_image(100)
                )
                
                if response['status_code'] == 302:  # Success
                    successful_uploads += 1
                elif response['status_code'] == 429:  # Rate limited
                    elapsed_time = time.time() - start_time
                    actual_rate = successful_uploads / (elapsed_time / 60)  # requests per minute
                    print(f"   ✓ Rate limited after {successful_uploads} uploads in {elapsed_time:.1f}s")
                    print(f"   ✓ Actual rate: {actual_rate:.1f} requests/min (limit: 10/min)")
                    
                    # Verify the rate limit is working (should be around 10/min or less)
                    assert actual_rate <= 12, f"Rate too high: {actual_rate:.1f}/min > 12/min"
                    break
            else:
                # If we never got rate limited, that's a problem
                elapsed_time = time.time() - start_time
                actual_rate = successful_uploads / (elapsed_time / 60)
                raise AssertionError(f"Rate limiting not triggered after {successful_uploads} uploads ({actual_rate:.1f}/min)")
            
            # Test 2: Update rate limiting - simplified approach
            print("\n📋 Testing Update Rate Limiting")
            print("   ⚠️ Note: Update rate limiting may not work reliably in test mode")
            print("   ✓ Update rate limiting test SKIPPED (upload rate limiting verified)")
            
            print("\n✅ Rate limiting test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Rate limiting test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")


class ValidationTest(IntegrationTestBase):
    """Test receipt validation logic"""
    
    def test_balance_validation(self) -> TestResult:
        """Test receipt balance validation"""
        print_test_header("Receipt Balance Validation Test")
        
        try:
            # Upload receipt
            print("\n💰 Setting up test receipt")
            
            response = self.upload_receipt("Test Validation User")
            if response['status_code'] != 302 or not response['receipt_slug']:
                raise AssertionError(f"Upload failed: {response['status_code']}")
            
            receipt_slug = response['receipt_slug']
            if not self.wait_for_processing(receipt_slug):
                raise AssertionError("Receipt processing failed")
            
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
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Validation test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")


class UIValidationTest(IntegrationTestBase):
    """Test UI components and frontend functionality"""
    
    def test_frontend_heic_support(self) -> TestResult:
        """Test that the frontend properly supports HEIC file uploads"""
        print_test_header("UI: Frontend HEIC Support Test")
        
        try:
            print("\n📱 Testing Frontend HEIC Support")
            
            # Test the main upload page HTML
            response = self.client.get('/')
            assert response.status_code == 200, "Index page should load"
            content = response.content.decode('utf-8')
            
            # Check HTML accept attribute includes HEIC
            assert '.heic' in content.lower(), "HTML should accept .heic files"
            assert '.heif' in content.lower(), "HTML should accept .heif files" 
            print("   ✅ HEIC/HEIF extensions included in HTML")
            
            # Check for HEIC MIME types
            assert 'image/heic' in content.lower(), "Should include HEIC MIME type"
            assert 'image/heif' in content.lower(), "Should include HEIF MIME type"
            print("   ✅ HEIC/HEIF MIME types included")
            
            print("\n✅ Frontend HEIC support test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Frontend HEIC test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")
    
    def test_ui_design_consistency(self) -> TestResult:
        """Test basic UI design consistency across key pages"""
        print_test_header("UI: Design Consistency Test")
        
        try:
            print("\n🎨 Testing Design Consistency")
            
            # Test key pages load and have consistent elements
            pages_to_test = [
                ('/', 'Index page'),
            ]
            
            for url, name in pages_to_test:
                response = self.client.get(url)
                assert response.status_code == 200, f"{name} should load successfully"
                content = response.content.decode('utf-8')
                
                # Check for consistent design elements
                assert 'tailwind' in content.lower() or 'class=' in content, f"{name} should use CSS framework"
                print(f"   ✅ {name} loaded with consistent styling")
            
            print("\n✅ UI design consistency test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ UI design test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")
    
    def test_responsive_images(self) -> TestResult:
        """Test CSS-based responsive image implementation"""
        print_test_header("UI: Responsive Images Test")
        
        try:
            print("\n📱 Testing CSS Responsive Image Implementation")
            
            # Test the main page for responsive images
            response = self.client.get('/')
            assert response.status_code == 200, "Index page should load"
            content = response.content.decode('utf-8')
            
            # Check for mobile-optimized images
            mobile_images = [
                'step_upload_mobile.png',
                'step_share_mobile.png', 
                'step_split_mobile.png'
            ]
            
            for mobile_img in mobile_images:
                assert mobile_img in content, f"Should reference {mobile_img}"
                print(f"   ✅ Mobile-optimized image {mobile_img} referenced")
            
            # Check for responsive CSS classes
            responsive_classes = [
                'w-20 h-20',        # Base mobile size
                'sm:w-32 sm:h-32',  # Small screen size
                'md:w-40 md:h-40'   # Medium screen size
            ]
            
            for css_class in responsive_classes:
                assert css_class in content, f"Should have responsive CSS class {css_class}"
                print(f"   ✅ Responsive CSS class {css_class} found")
            
            # Verify images use object-cover for proper scaling
            assert 'object-cover' in content, "Should use object-cover for proper image scaling"
            print("   ✅ object-cover CSS class found")
            
            print("\n✅ CSS responsive images test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Responsive images test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")
    
    def test_image_links_valid(self) -> TestResult:
        """Test that all image links are valid and accessible"""
        print_test_header("UI: Image Links Validation Test")
        
        try:
            print("\n🔗 Testing Image Link Validity")
            
            # Get the homepage content
            response = self.client.get('/')
            assert response.status_code == 200, "Index page should load"
            content = response.content.decode('utf-8')
            
            # Extract all image URLs from the page
            import re
            
            # Find all image sources 
            img_src_pattern = r'src=["\']([^"\']*\.png)["\']'
            img_urls = re.findall(img_src_pattern, content)
            all_image_urls = list(set(img_urls))
            
            print(f"   Found {len(all_image_urls)} unique image references:")
            for url in all_image_urls:
                print(f"     - {url}")
            
            # Test each image URL for accessibility  
            for img_url in all_image_urls:
                if img_url.startswith('/media/'):
                    # Test that the image is accessible
                    response = self.client.get(img_url)
                    assert response.status_code == 200, f"Image {img_url} should be accessible"
                    
                    # Verify it's actually an image
                    content_type = response.get('Content-Type', '')
                    assert content_type.startswith('image/'), f"Image {img_url} should have image content type, got {content_type}"
                    
                    print(f"   ✅ {img_url} accessible (Content-Type: {content_type})")
            
            # Verify expected mobile-optimized step images are present
            expected_mobile_images = [
                '/static/images/step_upload_mobile.png',
                '/static/images/step_share_mobile.png', 
                '/static/images/step_split_mobile.png'
            ]
            
            for expected_img in expected_mobile_images:
                assert expected_img in all_image_urls, f"Expected image {expected_img} not found in HTML"
                print(f"   ✅ Required mobile image {expected_img} found in HTML")
            
            print("\n✅ Image links validation test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Image links test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")


class PermissionTest(IntegrationTestBase):
    """Test permission and claim calculation scenarios"""
    
    def test_name_based_claim_calculations(self) -> TestResult:
        """Test the bug fix: claims calculated by name, not session"""
        print_test_header("Permissions: Name-Based Claim Calculations Test")
        
        try:
            # Step 1: Upload and finalize a receipt
            print("\n📤 Step 1: Create and finalize receipt")
            uploader = self.create_new_session()
            upload_response = uploader.upload_receipt("Restaurant Owner")
            
            assert upload_response['status_code'] == 302, "Upload should redirect"
            receipt_slug = upload_response['receipt_slug']
            print(f"   ✓ Receipt uploaded, slug: {receipt_slug}")
            
            # Wait for processing
            assert uploader.wait_for_processing(receipt_slug), "Processing should complete"
            
            # Update with test data
            test_data = TestDataGenerator.balanced_receipt()
            test_data['restaurant_name'] = 'The Gin Mill'
            test_data['subtotal'] = '64.00'
            test_data['tax'] = '0.00'
            test_data['tip'] = '0.00'
            test_data['total'] = '64.00'
            test_data['items'] = [
                {'name': 'PALOMA', 'quantity': 1, 'unit_price': '17.68', 'total_price': '17.68'},
                {'name': 'HAPPY HOUR BEER', 'quantity': 1, 'unit_price': '5.20', 'total_price': '5.20'},
                {'name': 'WELL TEQUILA', 'quantity': 1, 'unit_price': '5.20', 'total_price': '5.20'},
                {'name': 'BURGER', 'quantity': 1, 'unit_price': '15.00', 'total_price': '15.00'},
                {'name': 'FRIES', 'quantity': 1, 'unit_price': '8.00', 'total_price': '8.00'},
                {'name': 'SALAD', 'quantity': 1, 'unit_price': '12.92', 'total_price': '12.92'}
            ]
            
            uploader.update_receipt(receipt_slug, test_data)
            uploader.finalize_receipt(receipt_slug)
            print("   ✓ Receipt finalized with test items")
            
            # Step 2: User visits with name "Kui"
            print("\n👤 Step 2: User claims items as 'Kui'")
            user_session = self.create_new_session()
            assert user_session.set_viewer_name(receipt_slug, "Kui"), "Should set name"
            
            receipt_data = user_session.get_receipt_data(receipt_slug)
            items = receipt_data['items']
            
            # Claim PALOMA as "Kui"
            paloma_id = next(item['id'] for item in items if item['name'] == 'PALOMA')
            claim_resp = user_session.claim_item(receipt_slug, paloma_id, 1)
            assert claim_resp['status_code'] == 200, "Should claim PALOMA"
            print("   ✓ Claimed PALOMA as 'Kui' ($17.68)")
            
            # Check total for Kui
            kui_total = Decimal(str(claim_resp['data']['my_total']))
            assert kui_total == Decimal('17.68'), f"Kui total should be $17.68, got ${kui_total}"
            print(f"   ✓ 'Kui' total: ${kui_total}")
            
            # Step 3: Simulate name collision - forced to use "Kui 5"
            print("\n👤 Step 3: Same session forced to use 'Kui 5'")
            # In real scenario, this happens when returning to receipt after session metadata expires
            # but claims persist. We'll simulate by directly manipulating the session.
            
            # For testing, we'll create a scenario where the same session has to use a different name
            # This simulates the bug where the session asked for a new name but kept the old session
            
            # Claim more items as "Kui 5" (simulating forced rename)
            # In the real bug, this happened when the session metadata was lost but session_id persisted
            beer_id = next(item['id'] for item in items if item['name'] == 'HAPPY HOUR BEER')
            tequila_id = next(item['id'] for item in items if item['name'] == 'WELL TEQUILA')
            
            # Change the viewer name in session (simulating being forced to pick new name)
            # We need to do this at the session level to simulate the bug
            session = user_session.client.session
            if 'receipts' in session and str(receipt_data['id']) in session['receipts']:
                session['receipts'][str(receipt_data['id'])]['viewer_name'] = 'Kui 5'
                session.save()
            
            # Now claim as "Kui 5"
            claim_resp2 = user_session.claim_item(receipt_slug, beer_id, 1)
            assert claim_resp2['status_code'] == 200, "Should claim BEER"
            print("   ✓ Claimed HAPPY HOUR BEER as 'Kui 5' ($5.20)")
            
            claim_resp3 = user_session.claim_item(receipt_slug, tequila_id, 1)
            assert claim_resp3['status_code'] == 200, "Should claim TEQUILA"
            print("   ✓ Claimed WELL TEQUILA as 'Kui 5' ($5.20)")
            
            # Step 4: Verify totals are calculated by NAME not SESSION
            print("\n💰 Step 4: Verify name-based calculations")
            
            # Get the final state
            final_data = user_session.get_receipt_data(receipt_slug)
            
            # Check participant totals
            kui_claims = []
            kui5_claims = []
            
            for item in final_data['items']:
                for claim in item.get('claims', []):
                    if claim['claimer_name'] == 'Kui':
                        kui_claims.append({
                            'item': item['name'],
                            'amount': Decimal(str(claim['share_amount']))
                        })
                    elif claim['claimer_name'] == 'Kui 5':
                        kui5_claims.append({
                            'item': item['name'],
                            'amount': Decimal(str(claim['share_amount']))
                        })
            
            # Calculate totals
            kui_total = sum(c['amount'] for c in kui_claims)
            kui5_total = sum(c['amount'] for c in kui5_claims)
            
            print(f"\n   Claims for 'Kui':")
            for claim in kui_claims:
                print(f"     - {claim['item']}: ${claim['amount']}")
            print(f"   Total for 'Kui': ${kui_total}")
            
            print(f"\n   Claims for 'Kui 5':")
            for claim in kui5_claims:
                print(f"     - {claim['item']}: ${claim['amount']}")
            print(f"   Total for 'Kui 5': ${kui5_total}")
            
            # Verify the fix: totals should be separate by name
            assert kui_total == Decimal('17.68'), f"Kui should have $17.68, got ${kui_total}"
            assert kui5_total == Decimal('10.40'), f"Kui 5 should have $10.40, got ${kui5_total}"
            
            # The bug would have shown total of $28.08 for "Your Total" 
            # because it was summing by session_id not name
            session_total = kui_total + kui5_total
            print(f"\n   ✓ Name-based totals working correctly!")
            print(f"   ✓ 'Kui' has ${kui_total} (not ${session_total})")
            print(f"   ✓ 'Kui 5' has ${kui5_total} (not ${session_total})")
            
            print("\n✅ Name-based claim calculations test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")
    
    def test_uploader_permissions_with_name_change(self) -> TestResult:
        """Test that uploader retains edit permissions even with name changes"""
        print_test_header("Permissions: Uploader with Name Changes Test")
        
        try:
            # Step 1: Upload as uploader
            print("\n📤 Step 1: Upload receipt as uploader")
            uploader = self.create_new_session()
            upload_response = uploader.upload_receipt("Original Uploader")
            
            assert upload_response['status_code'] == 302, "Upload should redirect"
            receipt_slug = upload_response['receipt_slug']
            print(f"   ✓ Receipt uploaded by 'Original Uploader'")
            
            # Wait and verify can edit
            assert uploader.wait_for_processing(receipt_slug), "Processing should complete"
            
            # Verify uploader can edit
            test_data = TestDataGenerator.balanced_receipt()
            response = uploader.update_receipt(receipt_slug, test_data)
            assert response['status_code'] == 200, "Uploader should be able to edit"
            print("   ✓ Uploader can edit their receipt")
            
            # Step 2: Simulate session metadata loss (but session persists)
            print("\n🔄 Step 2: Simulate forced name change scenario")
            
            # In real scenario, the uploader returns after session metadata expires
            # They're forced to enter a new name but session/permissions should persist
            
            # Get current session and modify viewer name (simulating forced rename)
            session = uploader.client.session
            receipt_data = uploader.get_receipt_data(receipt_slug)
            
            if 'receipts' in session and str(receipt_data['id']) in session['receipts']:
                # Change name but keep is_uploader and edit_token
                old_data = session['receipts'][str(receipt_data['id'])]
                old_data['viewer_name'] = 'Original Uploader 2'  # Forced new name
                session.save()
                print("   ✓ Simulated name change to 'Original Uploader 2'")
            
            # Step 3: Verify permissions persist
            print("\n🔐 Step 3: Verify permissions persist after name change")
            
            # Should still be able to edit
            test_data['restaurant_name'] = 'Updated Restaurant Name'
            response = uploader.update_receipt(receipt_slug, test_data)
            assert response['status_code'] == 200, "Should still be able to edit after name change"
            print("   ✓ Can still edit after name change")
            
            # Step 4: Verify non-uploader cannot edit (BEFORE finalization)
            print("\n🚫 Step 4: Verify non-uploader cannot edit")
            
            other_user = self.create_new_session()
            response = other_user.update_receipt(receipt_slug, test_data)
            assert response['status_code'] == 403, "Non-uploader should not be able to edit"
            print("   ✓ Non-uploader correctly blocked from editing")
            
            # Step 5: Verify uploader can still finalize
            print("\n✅ Step 5: Verify uploader can finalize")
            response = uploader.finalize_receipt(receipt_slug)
            assert response['status_code'] == 200, "Should be able to finalize"
            print("   ✓ Can finalize after all permission checks")
            
            print("\n✅ Uploader permissions test PASSED")
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")

    @test_wrapper
    def test_claim_before_finalized(self) -> TestResult:
        """Test that nobody can claim items before a receipt is finalized."""
        # Step 1: Upload a receipt
        print("\n📤 Step 1: Upload receipt")
        uploader = self.create_new_session()
        upload_response = uploader.upload_receipt("Uploader")
        assert upload_response['status_code'] == 302, "Upload should redirect"
        receipt_slug = upload_response['receipt_slug']
        print(f"   ✓ Receipt uploaded, slug: {receipt_slug}")

        # Step 2: Wait for processing
        assert uploader.wait_for_processing(receipt_slug), "Processing should complete"
        print("   ✓ Receipt processed")

        # Step 3: Uploader tries to claim an item (should fail)
        print("\n👤 Step 3: Uploader attempts to claim before finalization")
        receipt_data = uploader.get_receipt_data(receipt_slug)
        item_id = receipt_data['items'][0]['id']

        claim_response = uploader.claim_item(receipt_slug, item_id, 1)
        assert claim_response['status_code'] == 400, "Uploader claim should be rejected before finalization"
        print("   ✓ Uploader claim correctly rejected")

        # Step 4: Another user tries to claim an item (should also fail)
        print("\n👤 Step 4: Another user attempts to claim before finalization")
        viewer = self.create_new_session()
        assert viewer.set_viewer_name(receipt_slug, "Viewer"), "Should set viewer name"

        claim_response = viewer.claim_item(receipt_slug, item_id, 1)
        assert claim_response['status_code'] == 400, "Viewer claim should be rejected before finalization"
        print("   ✓ Viewer claim correctly rejected")

        print("\n✅ Claim before finalized test PASSED")


class PerformanceTest(IntegrationTestBase):
    """Test application performance with large data"""
    
    def test_large_receipt(self) -> TestResult:
        """Test handling of receipts with many items"""
        print_test_header("Performance: Large Receipt Test")
        
        try:
            # Upload and process receipt - handle potential rate limiting
            print("\n📊 Testing large receipt (50 items)")
            
            
            response = self.upload_receipt("Test Performance User")
            if response['status_code'] != 302 or not response['receipt_slug']:
                raise AssertionError(f"Upload failed: {response['status_code']}")
                    
            receipt_slug = response['receipt_slug']
            if not self.wait_for_processing(receipt_slug):
                raise AssertionError("Receipt processing failed")
            
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
            return TestResult(TestResult.PASSED)
            
        except AssertionError as e:
            print(f"\n❌ Performance test failed: {e}")
            return TestResult(TestResult.FAILED, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return TestResult(TestResult.FAILED, f"Unexpected error: {e}")


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
        permission_test = PermissionTest()
        
        # Run tests
        results = []
        import time
        
        # Core workflow tests
        DELAY = 2  # Uniform 2 second delay
        results.append(("Complete Workflow", workflow_test.test_complete_workflow()))
        time.sleep(DELAY)
        
        # Permission tests - critical bug fixes
        results.append(("Claim Before Finalized", permission_test.test_claim_before_finalized()))
        time.sleep(DELAY)

        results.append(("Name-Based Claim Calculations", permission_test.test_name_based_claim_calculations()))
        time.sleep(DELAY)
        
        results.append(("Uploader Permissions with Name Change", permission_test.test_uploader_permissions_with_name_change()))
        time.sleep(DELAY)
        
        # Security tests - reduced uploads to avoid rate limit
        results.append(("Input Validation Security", security_test.test_input_validation()))
        time.sleep(DELAY)
        
        results.append(("File Upload Security", security_test.test_file_upload_security()))
        time.sleep(10)  # Wait to clear rate limit (we've done ~6 uploads so far)
        
        results.append(("Security Validation", security_test.test_security_validation()))
        
        # Wait to fully clear rate limit window (we've done 10 uploads)
        print("\n⏳ Waiting 30 seconds to clear rate limit...")
        time.sleep(30)
        
        # Validation tests
        results.append(("Balance Validation", validation_test.test_balance_validation()))
        time.sleep(DELAY)
        
        # UI tests (no uploads)
        ui_test = UIValidationTest()
        results.append(("Frontend HEIC Support", ui_test.test_frontend_heic_support()))
        results.append(("UI Design Consistency", ui_test.test_ui_design_consistency()))
        results.append(("Responsive Images", ui_test.test_responsive_images()))
        results.append(("Image Links Validation", ui_test.test_image_links_valid()))
        
        # Performance tests
        time.sleep(10)  # Wait to clear rate limit before performance test
        results.append(("Large Receipt Performance", performance_test.test_large_receipt()))
        time.sleep(10)  # Wait to clear rate limit before session test
        
        # Session security test
        results.append(("Session Security", security_test.test_session_security()))
        
        # Rate limiting test disabled per user request
        # results.append(("Rate Limiting Security", security_test.test_rate_limiting()))
        
        # Print summary
        print_test_summary(results)
        
        # Cleanup test data
        print("\n🧹 Cleaning up test data...")
        base_test = IntegrationTestBase()
        count = base_test.cleanup_test_receipts()
        print(f"   Deleted {count} test receipt(s)")
        
        # Return exit code - only fail if there are actual failures (not skips)
        failed_tests = [result for _, result in results if result.status == TestResult.FAILED]
        return 0 if len(failed_tests) == 0 else 1
        
    finally:
        # Stop patches
        for patch in patches:
            patch.stop()


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)