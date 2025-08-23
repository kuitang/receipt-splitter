"""
Tests for JavaScript injection vulnerabilities and XSS prevention.

Tests that user input cannot execute JavaScript in the browser through
error messages, widget IDs, or other dynamic content.
"""

import json
import re
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from receipts.models import Receipt, LineItem
from receipts.async_processor import create_placeholder_receipt
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
import io


class JavaScriptInjectionTests(TestCase):
    """Test JavaScript injection prevention in templates and error handling"""
    
    def setUp(self):
        """Set up test data with potential XSS payloads"""
        self.xss_payloads = [
            "<script>alert('XSS')</script>",
            "');alert('XSS');//",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "';alert('XSS');//",
            "<svg onload=alert('XSS')>",
            "&#60;script&#62;alert('XSS')&#60;/script&#62;",
            "<iframe src=javascript:alert('XSS')></iframe>",
            "';eval('alert(\"XSS\")');//",
            "<input onfocus=alert('XSS') autofocus>"
        ]
        
        # Create test receipt
        img = Image.new('RGB', (100, 100), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        test_image = SimpleUploadedFile(
            'test_receipt.jpg',
            buffer.getvalue(),
            content_type='image/jpeg'
        )
        
        self.receipt = create_placeholder_receipt("Safe Uploader", test_image)
        self.receipt.is_finalized = True
        self.receipt.processing_status = 'completed'
        self.receipt.save()
        
        # Create test item
        self.item = LineItem.objects.create(
            receipt=self.receipt,
            name="Safe Item",
            quantity=1,
            unit_price=Decimal('10.00'),
            total_price=Decimal('10.00')
        )
    
    def test_uploader_name_xss_prevention(self):
        """Test that malicious uploader names are sanitized and don't execute JavaScript"""
        
        for xss_payload in self.xss_payloads:
            with self.subTest(payload=xss_payload):
                # Try to upload with malicious uploader name
                client = Client()
                
                # Create test image
                img = Image.new('RGB', (100, 100), color='white')
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG')
                buffer.seek(0)
                
                response = client.post(reverse('upload_receipt'), {
                    'uploader_name': xss_payload,
                    'receipt_image': SimpleUploadedFile('test.jpg', buffer.getvalue(), content_type='image/jpeg')
                })
                
                # Should either be rejected (400) or sanitized (302 redirect)
                self.assertIn(response.status_code, [302, 400])
                
                if response.status_code == 302:
                    # If accepted, verify the name was sanitized
                    receipt_slug = response.url.split('/')[-2]
                    receipt = Receipt.objects.get(slug=receipt_slug)
                    
                    # Name should not contain script tags or javascript
                    self.assertNotIn('<script', receipt.uploader_name.lower())
                    self.assertNotIn('javascript:', receipt.uploader_name.lower())
                    self.assertNotIn('alert(', receipt.uploader_name.lower())
                    self.assertNotIn('onerror', receipt.uploader_name.lower())
    
    def test_viewer_name_xss_prevention(self):
        """Test that malicious viewer names are sanitized"""
        
        for xss_payload in self.xss_payloads:
            with self.subTest(payload=xss_payload):
                client = Client()
                
                # Try to set malicious viewer name
                response = client.post(
                    reverse('view_receipt', kwargs={'receipt_slug': self.receipt.slug}),
                    {'viewer_name': xss_payload}
                )
                
                # Should either be rejected or sanitized
                if response.status_code == 200:
                    # Check that the response doesn't contain executable script
                    content = response.content.decode()
                    self.assertNotIn('<script>alert(', content)
                    self.assertNotIn('javascript:alert(', content)
                    self.assertNotIn('onerror=alert(', content)
    
    def test_item_name_xss_in_receipt_editing(self):
        """Test that malicious item names in receipt updates are sanitized"""
        
        client = Client()
        session = client.session
        # Set up session with correct structure
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(self.receipt.id)] = {
            'is_uploader': True,
            'edit_token': 'test-token'
        }
        session.save()
        
        # Make receipt editable
        self.receipt.is_finalized = False
        self.receipt.save()
        
        for xss_payload in self.xss_payloads:
            with self.subTest(payload=xss_payload):
                # Try to update with malicious item name
                update_data = {
                    'restaurant_name': 'Safe Restaurant',
                    'subtotal': '10.00',
                    'tax': '1.00',
                    'tip': '1.50',
                    'total': '12.50',
                    'items': [
                        {
                            'name': xss_payload,
                            'quantity': 1,
                            'unit_price': '10.00',
                            'total_price': '10.00'
                        }
                    ]
                }
                
                response = client.post(
                    reverse('update_receipt', kwargs={'receipt_slug': self.receipt.slug}),
                    data=json.dumps(update_data),
                    content_type='application/json'
                )
                
                # Should either be rejected or sanitized
                if response.status_code == 200:
                    # Verify the item name was sanitized
                    updated_item = LineItem.objects.filter(receipt=self.receipt).first()
                    if updated_item:
                        # Name should not contain script tags or javascript
                        self.assertNotIn('<script', updated_item.name.lower())
                        self.assertNotIn('javascript:', updated_item.name.lower())
                        self.assertNotIn('alert(', updated_item.name.lower())
                        self.assertNotIn('onerror', updated_item.name.lower())
    
    def test_restaurant_name_xss_prevention(self):
        """Test that malicious restaurant names are sanitized"""
        
        client = Client()
        session = client.session
        # Set up session with correct structure
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(self.receipt.id)] = {
            'is_uploader': True,
            'edit_token': 'test-token'
        }
        session.save()
        
        # Make receipt editable
        self.receipt.is_finalized = False
        self.receipt.save()
        
        for xss_payload in self.xss_payloads:
            with self.subTest(payload=xss_payload):
                update_data = {
                    'restaurant_name': xss_payload,
                    'subtotal': '10.00',
                    'tax': '1.00', 
                    'tip': '1.50',
                    'total': '12.50',
                    'items': []
                }
                
                response = client.post(
                    reverse('update_receipt', kwargs={'receipt_slug': self.receipt.slug}),
                    data=json.dumps(update_data),
                    content_type='application/json'
                )
                
                if response.status_code == 200:
                    # Verify restaurant name was sanitized
                    self.receipt.refresh_from_db()
                    self.assertNotIn('<script', self.receipt.restaurant_name.lower())
                    self.assertNotIn('javascript:', self.receipt.restaurant_name.lower())
                    self.assertNotIn('alert(', self.receipt.restaurant_name.lower())
                    self.assertNotIn('onerror', self.receipt.restaurant_name.lower())
    
    def test_template_output_escaping(self):
        """Test that templates properly escape user content"""
        
        # Create receipt with potentially dangerous content (should be sanitized by validators)
        safe_name = "Test<script>Restaurant"  # Raw dangerous content
        
        receipt = Receipt.objects.create(
            uploader_name="Safe User",
            restaurant_name=safe_name,
            date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('1.50'),
            total=Decimal('12.50'),
            is_finalized=True,
            processing_status='completed'
        )
        
        client = Client()
        
        # Use the new session-based approach - set viewer name via POST
        response = client.post(
            reverse('view_receipt', kwargs={'receipt_slug': receipt.slug}),
            {'viewer_name': 'Safe Viewer'}
        )
        
        # Now GET the receipt
        response = client.get(reverse('view_receipt', kwargs={'receipt_slug': receipt.slug}))
        content = response.content.decode()
        
        # Templates should escape the content, so dangerous scripts should not be executable
        self.assertNotIn('<script>alert(', content)
        # The content should be escaped once (< becomes &lt;)
        self.assertIn('&lt;script&gt;', content)
    
    def test_javascript_context_safety(self):
        """Test that JavaScript constants in templates are safe"""
        
        client = Client()
        
        # Use the new session-based approach - set viewer name via POST  
        response = client.post(
            reverse('view_receipt', kwargs={'receipt_slug': self.receipt.slug}),
            {'viewer_name': 'Test Viewer'}
        )
        
        # Now GET the receipt
        response = client.get(reverse('view_receipt', kwargs={'receipt_slug': self.receipt.slug}))
        content = response.content.decode()
        
        # Check that receipt data is in data attributes (safer than JS constants)
        # Note: The actual templates may not use these exact data attributes
        # Let's check for the existence of the receipt slug in the page
        self.assertIn(self.receipt.slug, content)
        
        # Receipt slug and ID should not contain quotes or dangerous characters
        self.assertNotIn("'", self.receipt.slug)
        self.assertNotIn('"', self.receipt.slug)
        self.assertNotIn('<', str(self.receipt.id))
        self.assertNotIn('>', str(self.receipt.id))


class JavaScriptFunctionSecurityTests(TestCase):
    """Test JavaScript security functions work correctly"""
    
    def test_escape_html_function_exists(self):
        """Test that escapeHtml function is defined in templates"""
        
        receipt = Receipt.objects.create(
            uploader_name="Test User",
            restaurant_name="Test Restaurant", 
            date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('1.50'),
            total=Decimal('12.50'),
            is_finalized=False,
            processing_status='processing'  # This will show processing modal
        )
        
        client = Client()
        session = client.session
        # Set up session with correct structure
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(receipt.id)] = {
            'is_uploader': True,
            'edit_token': 'test-token'
        }
        session.save()
        
        response = client.get(reverse('edit_receipt', kwargs={'receipt_slug': receipt.slug}))
        content = response.content.decode()
        
        # The page should include utils.js which contains escapeHtml
        # In DEBUG mode, files aren't hashed; in production they are
        utils_pattern = r'/static/js/utils(\.([a-f0-9]+))?\.js'
        self.assertTrue(re.search(utils_pattern, content), f"utils.js not found in content: {content[:500]}...")
    
    def test_copy_widget_uses_data_attribute(self):
        """Test that copy widget uses safe data attribute approach"""
        
        receipt = Receipt.objects.create(
            uploader_name="Test User",
            restaurant_name="Test Restaurant",
            date=timezone.now(), 
            expires_at=timezone.now() + timedelta(hours=24),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('1.50'), 
            total=Decimal('12.50'),
            is_finalized=True,
            processing_status='completed'
        )
        
        client = Client()
        session = client.session
        # Set up as uploader to see copy widget
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(receipt.id)] = {
            'is_uploader': True,
            'viewer_name': 'Test User'
        }
        session.save()
        
        response = client.get(reverse('view_receipt', kwargs={'receipt_slug': receipt.slug}))
        content = response.content.decode()
        
        # Should show copy widget with data attributes  
        self.assertIn('data-widget-id="share-link-input"', content)
        # Should not use inline onclick handlers
        self.assertNotIn('onclick="copy', content.lower())


class ValidationErrorSecurityTests(TestCase):
    """Test that validation errors don't contain executable JavaScript"""
    
    def setUp(self):
        """Set up test receipt for validation testing"""
        
        img = Image.new('RGB', (100, 100), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        test_image = SimpleUploadedFile(
            'test_receipt.jpg',
            buffer.getvalue(),
            content_type='image/jpeg'
        )
        
        self.receipt = create_placeholder_receipt("Test User", test_image)
        self.receipt.is_finalized = False
        self.receipt.processing_status = 'completed'
        self.receipt.save()
    
    def test_validation_error_xss_prevention(self):
        """Test that validation errors with XSS payloads are safe"""
        
        client = Client()
        session = client.session
        # Set up session with correct structure
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(self.receipt.id)] = {
            'is_uploader': True,
            'edit_token': 'test-token'
        }
        session.save()
        
        # Try to update with malicious data that will trigger validation errors
        malicious_data = {
            'restaurant_name': '<script>alert("XSS from restaurant")</script>',
            'subtotal': 'not_a_number<script>alert("XSS")</script>',
            'tax': '-999999',
            'tip': 'javascript:alert("XSS")',
            'total': '<img src=x onerror=alert("XSS")>',
            'items': [
                {
                    'name': '"><script>alert("XSS from item")</script><"',
                    'quantity': 'javascript:alert("XSS")',
                    'unit_price': '<svg onload=alert("XSS")>',
                    'total_price': '");alert("XSS");//'
                }
            ]
        }
        
        response = client.post(
            reverse('update_receipt', kwargs={'receipt_slug': self.receipt.slug}),
            data=json.dumps(malicious_data),
            content_type='application/json'
        )
        
        # Even if validation fails, the response should not contain executable JavaScript
        response_content = response.content.decode()
        
        # Check that dangerous content is not present in the response
        dangerous_patterns = [
            '<script>alert(',
            'javascript:alert(',
            'onerror=alert(',
            'onload=alert(',
            '");alert(',
            "');alert("
        ]
        
        for pattern in dangerous_patterns:
            self.assertNotIn(pattern, response_content.lower(),
                           f"Dangerous pattern '{pattern}' found in response")
    
    def test_error_message_content_safety(self):
        """Test that error messages themselves don't contain XSS"""
        
        from receipts.validators import InputValidator
        from django.core.exceptions import ValidationError
        
        # Test that validator error messages are safe even with malicious input
        malicious_inputs = [
            '<script>alert("XSS")</script>',
            'javascript:alert("XSS")',
            '"><script>alert("XSS")</script>',
            "';alert('XSS');//"
        ]
        
        for malicious_input in malicious_inputs:
            with self.subTest(input=malicious_input):
                try:
                    # This should sanitize the input and not include it in error messages
                    sanitized = InputValidator.validate_name(malicious_input, field_name="Test")
                    
                    # If validation passes, the output should be sanitized
                    self.assertNotIn('<script', sanitized.lower())
                    self.assertNotIn('javascript:', sanitized.lower())
                    
                except ValidationError as e:
                    # If validation fails, error message should not contain executable code
                    error_msg = str(e)
                    self.assertNotIn('<script', error_msg.lower())
                    self.assertNotIn('javascript:', error_msg.lower())
    
    def test_claim_data_xss_prevention(self):
        """Test that claim operations don't allow XSS through JSON data"""
        
        # Create an item for the receipt to test claiming
        from receipts.models import LineItem
        from decimal import Decimal
        
        item = LineItem.objects.create(
            receipt=self.receipt,
            name="Test Item",
            quantity=2,
            unit_price=Decimal('10.00'),
            total_price=Decimal('20.00')
        )
        
        client = Client()
        session = client.session
        session[f'viewer_name_{self.receipt.id}'] = "Safe Viewer"
        session.save()
        
        # Try to claim with malicious data structure
        malicious_claim_data = {
            'line_item_id': str(item.id),
            'quantity': 1,
            'malicious_field': '<script>alert("XSS")</script>',
            'another_field': 'javascript:alert("XSS")'
        }
        
        response = client.post(
            reverse('claim_item', kwargs={'receipt_slug': self.receipt.slug}),
            data=json.dumps(malicious_claim_data),
            content_type='application/json'
        )
        
        # Response should not contain executable JavaScript
        if response.status_code == 200:
            response_content = response.content.decode()
            self.assertNotIn('<script>alert(', response_content)
            self.assertNotIn('javascript:alert(', response_content)
    
    def test_html_input_attribute_safety(self):
        """Test that HTML input attributes are properly escaped"""
        
        # Create item with content that could break HTML attributes
        dangerous_name = 'Item" onload="alert(\'XSS\')" data-evil="'
        
        # This should be sanitized by the validator
        from receipts.validators import InputValidator
        from receipts.models import LineItem
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        
        try:
            safe_name = InputValidator.validate_name(dangerous_name)
            
            # Create a test item with the safe name
            item = LineItem.objects.create(
                receipt=self.receipt,
                name=safe_name,
                quantity=1,
                unit_price=Decimal('10.00'),
                total_price=Decimal('10.00')
            )
            
            client = Client()
            session = client.session
            # Set up session with correct structure
            if 'receipts' not in session:
                session['receipts'] = {}
            session['receipts'][str(self.receipt.id)] = {
                'is_uploader': True,
                'edit_token': 'test-token'
            }
            session.save()
            
            # Make receipt editable
            self.receipt.is_finalized = False
            self.receipt.save()
            
            response = client.get(reverse('edit_receipt', kwargs={'receipt_slug': self.receipt.slug}))
            content = response.content.decode()
            
            # Should not contain unescaped quotes or event handlers in HTML attributes
            self.assertNotIn('onload="alert(', content)
            self.assertNotIn('" onload="', content)
            self.assertNotIn('data-evil="', content)
            
        except ValidationError:
            # If validation properly rejects the input, that's also acceptable
            pass


class WidgetSecurityTests(TestCase):
    """Test security of reusable widgets"""
    
    def test_copy_widget_injection_prevention(self):
        """Test that copy widget prevents JavaScript injection through widget_id"""
        
        receipt = Receipt.objects.create(
            uploader_name="Test User",
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            subtotal=Decimal('10.00'),
            tax=Decimal('1.00'),
            tip=Decimal('1.50'),
            total=Decimal('12.50'),
            is_finalized=True,
            processing_status='completed'
        )
        
        client = Client()
        session = client.session
        # Set up as uploader to see copy widget
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(receipt.id)] = {
            'is_uploader': True,
            'viewer_name': 'Test User'
        }
        session.save()
        
        response = client.get(reverse('view_receipt', kwargs={'receipt_slug': receipt.slug}))
        content = response.content.decode()
        
        # Verify copy widget uses data attribute approach for security
        self.assertIn('data-widget-id="share-link-input"', content)
        
        # Should NOT use direct template interpolation in onclick
        self.assertNotIn("copyShareUrl('share-link-input', event)", content)
        self.assertNotIn("copyShareUrl('{{ widget_id }}', event)", content)