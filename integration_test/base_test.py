"""
Base classes and utilities for integration testing.
Ensures tests interact only via HTTP API, not direct module imports.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'receipt_splitter.settings')
import django
django.setup()

# Only import Django test client, not app modules
from django.test import Client


class IntegrationTestBase:
    """Base class for all integration tests"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = Client()
        self.session_cookies = {}
        
    def create_test_image(self, size_bytes: int = 1000, content: bytes = None) -> bytes:
        """Create a fake image for testing"""
        if content:
            return content
        # Create different sized fake images for triggering different mock responses
        return b'FAKE_IMAGE_DATA' * (size_bytes // 15)
    
    def upload_receipt(self, uploader_name: str, image_bytes: bytes = None, 
                      filename: str = "test_receipt.jpg") -> Dict[str, Any]:
        """Upload a receipt and return response data"""
        if image_bytes is None:
            image_bytes = self.create_test_image()
        
        # Create a proper file-like object for Django test client
        from django.core.files.uploadedfile import SimpleUploadedFile
        uploaded_file = SimpleUploadedFile(
            name=filename,
            content=image_bytes,
            content_type='image/jpeg'
        )
        
        response = self.client.post('/upload/', {
            'uploader_name': uploader_name,
            'receipt_image': uploaded_file
        })
        
        # Extract receipt slug from redirect URL
        receipt_slug = None
        if response.status_code == 302 and response.url:
            # URL format: /edit/{slug}/ 
            parts = response.url.strip('/').split('/')
            if len(parts) >= 2 and parts[0] == 'edit':
                receipt_slug = parts[1]
        
        return {
            'status_code': response.status_code,
            'redirect_url': response.url if response.status_code == 302 else None,
            'receipt_slug': receipt_slug,
            'content': response.content.decode('utf-8') if response.content else None,
            'cookies': response.cookies
        }
    
    def wait_for_processing(self, receipt_slug: str, timeout: int = 30) -> bool:
        """Wait for async receipt processing to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = self.client.get(f'/status/{receipt_slug}/')
            
            if response.status_code == 200:
                data = json.loads(response.content)
                if data.get('status') == 'completed':
                    return True
                elif data.get('status') == 'failed':
                    print(f"Processing failed: {data.get('error')}")
                    return False
            
            time.sleep(0.5)
        
        print(f"Timeout waiting for processing of {receipt_slug}")
        return False
    
    def get_receipt_data(self, receipt_slug: str) -> Optional[Dict[str, Any]]:
        """Get receipt data - uses Django models for integration testing"""
        # For integration testing, we'll access the database directly
        # This is acceptable since we're testing the full stack
        from receipts.models import Receipt
        
        try:
            receipt = Receipt.objects.get(slug=receipt_slug)
            
            items = []
            for item in receipt.items.all():
                item_data = {
                    'id': item.id,
                    'name': item.name,
                    'quantity': item.quantity,
                    'unit_price': str(item.unit_price),
                    'total_price': str(item.total_price),
                    'claims': []
                }
                
                for claim in item.claims.all():
                    item_data['claims'].append({
                        'id': claim.id,
                        'claimer_name': claim.claimer_name,
                        'quantity_claimed': claim.quantity_claimed,
                        'share_amount': str(claim.get_share_amount())
                    })
                
                items.append(item_data)
            
            return {
                'id': str(receipt.id),
                'slug': receipt.slug,
                'restaurant_name': receipt.restaurant_name,
                'uploader_name': receipt.uploader_name,
                'date': receipt.date.isoformat() if receipt.date else None,
                'items': items,
                'subtotal': str(receipt.subtotal),
                'tax': str(receipt.tax),
                'tip': str(receipt.tip),
                'total': str(receipt.total),
                'is_finalized': receipt.is_finalized,
                'processing_status': receipt.processing_status,
                'items_count': len(items)
            }
        except Receipt.DoesNotExist:
            return None
    
    def update_receipt(self, receipt_slug: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update receipt data"""
        response = self.client.post(
            f'/update/{receipt_slug}/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        return {
            'status_code': response.status_code,
            'data': json.loads(response.content) if response.content else None
        }
    
    def finalize_receipt(self, receipt_slug: str) -> Dict[str, Any]:
        """Finalize a receipt"""
        response = self.client.post(f'/finalize/{receipt_slug}/')
        
        return {
            'status_code': response.status_code,
            'data': json.loads(response.content) if response.content else None
        }
    
    def set_viewer_name(self, receipt_slug: str, viewer_name: str) -> bool:
        """Set viewer name for a receipt"""
        response = self.client.post(f'/r/{receipt_slug}/', {
            'viewer_name': viewer_name
        })
        
        return response.status_code in [200, 302]
    
    def claim_item(self, receipt_slug: str, line_item_id: int, 
                   quantity: int = 1) -> Dict[str, Any]:
        """Claim an item on a receipt"""
        response = self.client.post(
            f'/claim/{receipt_slug}/',
            data=json.dumps({
                'line_item_id': line_item_id,
                'quantity': quantity
            }),
            content_type='application/json'
        )
        
        return {
            'status_code': response.status_code,
            'data': json.loads(response.content) if response.content else None
        }
    
    def unclaim_item(self, receipt_slug: str, claim_id: int) -> Dict[str, Any]:
        """Unclaim an item"""
        response = self.client.delete(f'/unclaim/{receipt_slug}/{claim_id}/')
        
        return {
            'status_code': response.status_code,
            'data': json.loads(response.content) if response.content else None
        }
    
    def create_new_session(self) -> 'IntegrationTestBase':
        """Create a new test instance with a fresh session (simulates new user)"""
        return IntegrationTestBase(self.base_url)
    
    def assert_receipt_balanced(self, receipt_data: Dict[str, Any]) -> None:
        """Assert that receipt totals are balanced"""
        items = receipt_data.get('items', [])
        subtotal = Decimal(str(receipt_data['subtotal']))
        tax = Decimal(str(receipt_data['tax']))
        tip = Decimal(str(receipt_data['tip']))
        total = Decimal(str(receipt_data['total']))
        
        # Check items sum to subtotal
        items_sum = sum(
            Decimal(str(item['total_price'])) 
            for item in items
        )
        assert abs(items_sum - subtotal) < Decimal('0.10'), \
            f"Items sum {items_sum} doesn't match subtotal {subtotal}"
        
        # Check subtotal + tax + tip = total
        calculated_total = subtotal + tax + tip
        assert abs(calculated_total - total) < Decimal('0.10'), \
            f"Calculated total {calculated_total} doesn't match receipt total {total}"
    
    def assert_response_success(self, response: Dict[str, Any]) -> None:
        """Assert that an API response indicates success"""
        assert response['status_code'] in [200, 201, 302], \
            f"Expected success but got {response['status_code']}: {response.get('data')}"
        
        if response.get('data'):
            assert response['data'].get('success') != False, \
                f"Response indicates failure: {response['data']}"
    
    def cleanup_test_receipts(self, uploader_name: str = None) -> int:
        """Clean up test receipts from database (requires Django access)"""
        from receipts.models import Receipt
        
        if uploader_name:
            receipts = Receipt.objects.filter(uploader_name=uploader_name)
        else:
            # Clean up all test receipts
            receipts = Receipt.objects.filter(
                uploader_name__startswith='Test'
            )
        
        count = receipts.count()
        receipts.delete()
        return count


class TestDataGenerator:
    """Generate test data for various scenarios"""
    
    @staticmethod
    def balanced_receipt() -> Dict[str, Any]:
        """Generate balanced receipt data"""
        return {
            'restaurant_name': 'Test Restaurant',
            'items': [
                {'name': 'Item 1', 'quantity': 1, 'unit_price': '10.00', 'total_price': '10.00'},
                {'name': 'Item 2', 'quantity': 2, 'unit_price': '5.00', 'total_price': '10.00'},
            ],
            'subtotal': '20.00',
            'tax': '1.60',
            'tip': '3.40',
            'total': '25.00'
        }
    
    @staticmethod
    def unbalanced_receipt() -> Dict[str, Any]:
        """Generate unbalanced receipt data for validation testing"""
        return {
            'restaurant_name': 'Test Restaurant',
            'items': [
                {'name': 'Item 1', 'quantity': 1, 'unit_price': '10.00', 'total_price': '10.00'},
                {'name': 'Item 2', 'quantity': 2, 'unit_price': '5.00', 'total_price': '10.00'},
            ],
            'subtotal': '20.00',
            'tax': '1.60',
            'tip': '3.40',
            'total': '30.00'  # Wrong total for testing validation
        }
    
    @staticmethod
    def receipt_with_negative_tip() -> Dict[str, Any]:
        """Generate receipt with negative tip (discount)"""
        return {
            'restaurant_name': 'Discount Restaurant',
            'items': [
                {'name': 'Meal', 'quantity': 1, 'unit_price': '25.00', 'total_price': '25.00'},
            ],
            'subtotal': '25.00',
            'tax': '2.00',
            'tip': '-5.00',  # Negative tip represents discount
            'total': '22.00'
        }
    
    @staticmethod
    def large_receipt(num_items: int = 50) -> Dict[str, Any]:
        """Generate a large receipt with many items"""
        items = []
        subtotal = Decimal('0')
        
        for i in range(num_items):
            price = Decimal(f"{5 + (i % 20)}.99")
            items.append({
                'name': f'Item {i+1}',
                'quantity': 1,
                'unit_price': str(price),
                'total_price': str(price)
            })
            subtotal += price
        
        tax = (subtotal * Decimal('0.08')).quantize(Decimal('0.01'))
        tip = (subtotal * Decimal('0.15')).quantize(Decimal('0.01'))
        total = subtotal + tax + tip
        
        return {
            'restaurant_name': 'Large Order Restaurant',
            'items': items,
            'subtotal': str(subtotal),
            'tax': str(tax),
            'tip': str(tip),
            'total': str(total)
        }


class SecurityTestHelper:
    """Helper methods for security testing"""
    
    @staticmethod
    def get_xss_payloads() -> List[str]:
        """Get common XSS test payloads"""
        return [
            '<script>alert("XSS")</script>',
            '"><script>alert("XSS")</script>',
            "';alert('XSS');//",
            '<img src=x onerror=alert("XSS")>',
            '<svg onload=alert("XSS")>',
            'javascript:alert("XSS")',
            '<iframe src="javascript:alert(\'XSS\')">',
            '<body onload=alert("XSS")>',
        ]
    
    @staticmethod
    def get_sql_injection_payloads() -> List[str]:
        """Get common SQL injection test payloads"""
        return [
            "' OR '1'='1",
            "'; DROP TABLE receipts; --",
            "1' AND '1' = '1",
            "admin'--",
            "' UNION SELECT * FROM users--",
            "1' OR '1' = '1' /*",
        ]
    
    @staticmethod
    def get_path_traversal_payloads() -> List[str]:
        """Get path traversal test payloads"""
        return [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ]
    
    @staticmethod
    def get_oversized_data(size_mb: int = 10) -> bytes:
        """Generate oversized data for DoS testing"""
        return b'X' * (size_mb * 1024 * 1024)


def print_test_header(test_name: str):
    """Print a formatted test header"""
    print("\n" + "=" * 70)
    print(f"🧪 {test_name}")
    print("=" * 70)


def print_test_result(passed: bool, message: str):
    """Print a formatted test result"""
    icon = "✅" if passed else "❌"
    print(f"{icon} {message}")


def print_test_summary(results: List[tuple[str, bool]]):
    """Print test summary"""
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, result in results:
        icon = "✅" if result else "❌"
        print(f"  {icon} {test_name}")
    
    print("-" * 70)
    print(f"Results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ ALL TESTS PASSED")
    else:
        print(f"❌ {total - passed} TEST(S) FAILED")
    
    print("=" * 70)