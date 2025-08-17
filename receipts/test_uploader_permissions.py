"""
Focused tests for uploader claim permissions on finalized receipts.

Tests the specific change that allows uploaders to claim items only after finalization.
"""

from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from receipts.models import Receipt, LineItem


class UploaderClaimPermissionTests(TestCase):
    """Test uploader claim permissions based on receipt finalization status"""
    
    def setUp(self):
        """Set up test data"""
        self.uploader_name = "Test Uploader"
        self.other_viewer = "Other Viewer"
        
        # Create test receipt
        self.receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            subtotal=Decimal('20.00'),
            tax=Decimal('2.00'),
            tip=Decimal('3.00'),
            total=Decimal('25.00'),
            is_finalized=False,  # Start unfinalized
            processing_status='completed'
        )
        
        # Create a test item
        self.item = LineItem.objects.create(
            receipt=self.receipt,
            name="Test Item",
            quantity=2,
            unit_price=Decimal('10.00'),
            total_price=Decimal('20.00')
        )
    
    def test_uploader_claim_visibility_logic(self):
        """Test the template logic for uploader claim visibility"""
        client = Client()
        
        # Test 1: Uploader on unfinalized receipt - should NOT see claims
        session = client.session
        session[f'viewer_name_{self.receipt.id}'] = self.uploader_name
        session['receipt_id'] = str(self.receipt.id)  # Makes them uploader
        session.save()
        
        response = client.get(reverse('view_receipt_by_slug',
                                    kwargs={'receipt_slug': self.receipt.slug}))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        # Verify context variables
        self.assertTrue(context['is_uploader'])
        self.assertFalse(context['receipt'].is_finalized)
        
        # Logic: viewer_name AND (not is_uploader OR receipt.is_finalized)
        # True AND (not True OR False) = True AND False = False
        should_show_claims = (context.get('viewer_name') and 
                            (not context['is_uploader'] or context['receipt'].is_finalized))
        self.assertFalse(should_show_claims)
        
        # Test 2: Finalize receipt - uploader should NOW see claims
        self.receipt.is_finalized = True
        self.receipt.save()
        
        response = client.get(reverse('view_receipt_by_slug',
                                    kwargs={'receipt_slug': self.receipt.slug}))
        
        context = response.context
        self.assertTrue(context['is_uploader'])
        self.assertTrue(context['receipt'].is_finalized)
        
        # Logic: viewer_name AND (not is_uploader OR receipt.is_finalized)
        # True AND (not True OR True) = True AND True = True
        should_show_claims = (context.get('viewer_name') and 
                            (not context['is_uploader'] or context['receipt'].is_finalized))
        self.assertTrue(should_show_claims)
        
        # Test 3: Non-uploader should always see claims (regardless of finalization)
        session = client.session
        session[f'viewer_name_{self.receipt.id}'] = self.other_viewer
        session['receipt_id'] = None  # Not the uploader
        session.save()
        
        # Test on finalized receipt
        response = client.get(reverse('view_receipt_by_slug',
                                    kwargs={'receipt_slug': self.receipt.slug}))
        context = response.context
        self.assertFalse(context['is_uploader'])
        
        should_show_claims = (context.get('viewer_name') and 
                            (not context['is_uploader'] or context['receipt'].is_finalized))
        self.assertTrue(should_show_claims)
        
        # Test on unfinalized receipt
        self.receipt.is_finalized = False
        self.receipt.save()
        
        response = client.get(reverse('view_receipt_by_slug',
                                    kwargs={'receipt_slug': self.receipt.slug}))
        context = response.context
        self.assertFalse(context['is_uploader'])
        
        should_show_claims = (context.get('viewer_name') and 
                            (not context['is_uploader'] or context['receipt'].is_finalized))
        self.assertTrue(should_show_claims)  # Non-uploaders always see claims
    
    def test_template_claim_controls_presence(self):
        """Test that claim controls appear/disappear based on the logic"""
        client = Client()
        
        # Set up as uploader
        session = client.session
        session['viewer_name'] = self.uploader_name
        session['receipt_id'] = str(self.receipt.id)
        session.save()
        
        # Test unfinalized receipt - no claim controls for uploader
        session = client.session
        session[f'viewer_name_{self.receipt.id}'] = self.uploader_name
        session['receipt_id'] = str(self.receipt.id)
        session.save()
        
        self.receipt.is_finalized = False
        self.receipt.save()
        
        response = client.get(reverse('view_receipt_by_slug',
                                    kwargs={'receipt_slug': self.receipt.slug}))
        content = response.content.decode()
        
        # Should not contain claim quantity inputs for uploader on unfinalized
        self.assertNotIn('claim-quantity', content)
        
        # Test finalized receipt - should have claim controls
        self.receipt.is_finalized = True
        self.receipt.save()
        
        response = client.get(reverse('view_receipt_by_slug',
                                    kwargs={'receipt_slug': self.receipt.slug}))
        content = response.content.decode()
        
        # Should contain claim quantity inputs
        self.assertIn('claim-quantity', content)
    
    def test_permission_logic_summary(self):
        """Summarize the permission logic in one comprehensive test"""
        
        test_cases = [
            # (is_uploader, is_finalized, should_show_claims)
            (True, False, False),   # Uploader on unfinalized - NO
            (True, True, True),     # Uploader on finalized - YES  
            (False, False, True),   # Non-uploader on unfinalized - YES
            (False, True, True),    # Non-uploader on finalized - YES
        ]
        
        for is_uploader, is_finalized, expected_show_claims in test_cases:
            with self.subTest(is_uploader=is_uploader, is_finalized=is_finalized):
                client = Client()
                session = client.session
                
                if is_uploader:
                    session[f'viewer_name_{self.receipt.id}'] = self.uploader_name
                    session['receipt_id'] = str(self.receipt.id)
                else:
                    session[f'viewer_name_{self.receipt.id}'] = self.other_viewer
                    session['receipt_id'] = None
                
                session.save()
                
                # Set receipt finalization status
                self.receipt.is_finalized = is_finalized
                self.receipt.save()
                
                response = client.get(reverse('view_receipt_by_slug',
                                            kwargs={'receipt_slug': self.receipt.slug}))
                context = response.context
                
                # Verify context
                self.assertEqual(context['is_uploader'], is_uploader)
                self.assertEqual(context['receipt'].is_finalized, is_finalized)
                
                # Test the actual logic
                viewer_name = context.get('viewer_name')
                actual_show_claims = viewer_name and (not context['is_uploader'] or context['receipt'].is_finalized)
                
                self.assertEqual(actual_show_claims, expected_show_claims,
                               f"Failed for is_uploader={is_uploader}, is_finalized={is_finalized}")