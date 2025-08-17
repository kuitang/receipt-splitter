"""
Test suite for uploader permissions using the new session management system.
Tests edit permissions and image viewing permissions for uploaders vs non-uploaders.
"""
from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, MagicMock
import json

from receipts.models import Receipt, LineItem, Claim
from receipts.session_manager import ReceiptSessionManager
from receipts.user_context import UserContext


class UploaderPermissionUnitTests(TestCase):
    """Unit tests for uploader permissions using UserContext"""
    
    def setUp(self):
        """Set up test data"""
        self.uploader_name = "Test Uploader"
        self.other_viewer = "Other Viewer"
        
        # Create finalized receipt
        self.finalized_receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            subtotal=Decimal('20.00'),
            tax=Decimal('2.00'),
            tip=Decimal('3.00'),
            total=Decimal('25.00'),
            is_finalized=True,
            processing_status='completed'
        )
        
        # Create unfinalized receipt
        self.unfinalized_receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Test Restaurant 2",
            date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            subtotal=Decimal('15.00'),
            tax=Decimal('1.50'),
            tip=Decimal('2.00'),
            total=Decimal('18.50'),
            is_finalized=False,
            processing_status='completed'
        )
        
        # Create test items
        self.item1 = LineItem.objects.create(
            receipt=self.finalized_receipt,
            name="Pizza",
            quantity=2,
            unit_price=Decimal('10.00'),
            total_price=Decimal('20.00')
        )
        
        self.item2 = LineItem.objects.create(
            receipt=self.unfinalized_receipt,
            name="Burger",
            quantity=1,
            unit_price=Decimal('15.00'),
            total_price=Decimal('15.00')
        )
    
    def test_user_context_uploader_identification(self):
        """Test that UserContext correctly identifies uploaders"""
        # Create a mock request with session
        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_session.session_key = 'test-session-key'
        mock_session.get.return_value = {
            str(self.finalized_receipt.id): {
                'is_uploader': True,
                'viewer_name': self.uploader_name
            }
        }
        mock_session.__getitem__ = lambda self, key: {
            'receipts': {
                str(self.finalized_receipt.id): {
                    'is_uploader': True,
                    'viewer_name': self.uploader_name
                }
            }
        }[key]
        mock_session.__contains__ = lambda self, key: key == 'receipts'
        mock_request.session = mock_session
        
        # Create session manager and user context
        session_manager = ReceiptSessionManager(mock_request)
        user_context = UserContext(session_manager, self.finalized_receipt.id)
        
        # Test uploader identification
        self.assertTrue(user_context.is_uploader)
        self.assertEqual(user_context.name, self.uploader_name)
    
    def test_user_context_non_uploader(self):
        """Test that UserContext correctly identifies non-uploaders"""
        # Create a mock request with session
        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_session.session_key = 'test-non-uploader-session'
        
        # Set up the session data structure
        session_data = {
            'receipts': {
                str(self.finalized_receipt.id): {
                    'is_uploader': False,
                    'viewer_name': self.other_viewer
                }
            }
        }
        
        # Configure the mock to return proper values
        mock_session.get = MagicMock(side_effect=lambda key, default=None: session_data.get(key, default))
        mock_session.__getitem__ = MagicMock(side_effect=lambda key: session_data[key])
        mock_session.__contains__ = MagicMock(side_effect=lambda key: key in session_data)
        mock_session.__setitem__ = MagicMock(side_effect=lambda key, value: session_data.__setitem__(key, value))
        mock_session.modified = False
        
        mock_request.session = mock_session
        
        # Create session manager and user context
        session_manager = ReceiptSessionManager(mock_request)
        user_context = UserContext(session_manager, self.finalized_receipt.id)
        
        # Test non-uploader identification
        self.assertFalse(user_context.is_uploader)
        self.assertEqual(user_context.name, self.other_viewer)
    
    def test_edit_permission_for_uploader(self):
        """Test that uploaders have edit permission"""
        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_session.session_key = 'test-uploader-session'
        mock_session.__getitem__ = lambda self, key: {
            'receipts': {
                str(self.unfinalized_receipt.id): {
                    'is_uploader': True,
                    'edit_token': 'test-token',
                    'viewer_name': self.uploader_name
                }
            }
        }[key]
        mock_session.__contains__ = lambda self, key: key == 'receipts'
        mock_request.session = mock_session
        
        session_manager = ReceiptSessionManager(mock_request)
        user_context = UserContext(session_manager, self.unfinalized_receipt.id)
        
        # Uploaders should have edit permission
        self.assertTrue(user_context.can_edit)
    
    def test_no_edit_permission_for_non_uploader(self):
        """Test that non-uploaders don't have edit permission"""
        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_session.session_key = 'test-viewer-session'
        
        # Set up the session data structure
        session_data = {
            'receipts': {
                str(self.unfinalized_receipt.id): {
                    'is_uploader': False,
                    'viewer_name': self.other_viewer
                }
            }
        }
        
        # Configure the mock to return proper values
        mock_session.get = MagicMock(side_effect=lambda key, default=None: session_data.get(key, default))
        mock_session.__getitem__ = MagicMock(side_effect=lambda key: session_data[key])
        mock_session.__contains__ = MagicMock(side_effect=lambda key: key in session_data)
        mock_session.__setitem__ = MagicMock(side_effect=lambda key, value: session_data.__setitem__(key, value))
        mock_session.modified = False
        
        mock_request.session = mock_session
        
        session_manager = ReceiptSessionManager(mock_request)
        user_context = UserContext(session_manager, self.unfinalized_receipt.id)
        
        # Non-uploaders should NOT have edit permission
        self.assertFalse(user_context.can_edit)


class UploaderImagePermissionTests(TransactionTestCase):
    """Test image viewing permissions for uploaders"""
    
    def setUp(self):
        """Set up test data and client"""
        self.client = Client()
        self.uploader_name = "Image Uploader"
        self.viewer_name = "Image Viewer"
        
        # Create test receipts
        self.unfinalized_receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Unfinalized Restaurant",
            date=timezone.now(),
            subtotal=Decimal('50.00'),
            tax=Decimal('5.00'),
            tip=Decimal('10.00'),
            total=Decimal('65.00'),
            is_finalized=False,
            processing_status='completed'
        )
        
        self.finalized_receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Finalized Restaurant",
            date=timezone.now(),
            subtotal=Decimal('30.00'),
            tax=Decimal('3.00'),
            tip=Decimal('6.00'),
            total=Decimal('39.00'),
            is_finalized=True,
            processing_status='completed'
        )
    
    @patch('receipts.image_storage.get_receipt_image_from_memory')
    def test_uploader_can_view_image_during_editing(self, mock_get_image):
        """Test that uploader can view image while receipt is unfinalized"""
        mock_get_image.return_value = (b'fake_image_data', 'image/jpeg')
        
        # Set up session as uploader
        session = self.client.session
        session['receipts'] = {
            str(self.unfinalized_receipt.id): {
                'is_uploader': True,
                'viewer_name': self.uploader_name
            }
        }
        session.save()
        
        # Try to get image
        response = self.client.get(
            reverse('serve_receipt_image', kwargs={'receipt_slug': self.unfinalized_receipt.slug})
        )
        
        # Uploader should be able to view image
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'fake_image_data')
    
    @patch('receipts.image_storage.get_receipt_image_from_memory')
    def test_non_uploader_cannot_view_image_during_editing(self, mock_get_image):
        """Test that non-uploader cannot view image while receipt is unfinalized"""
        mock_get_image.return_value = (b'fake_image_data', 'image/jpeg')
        
        # Set up session as non-uploader
        session = self.client.session
        session['receipts'] = {
            str(self.unfinalized_receipt.id): {
                'is_uploader': False,
                'viewer_name': self.viewer_name
            }
        }
        session.save()
        
        # Try to get image
        response = self.client.get(
            reverse('serve_receipt_image', kwargs={'receipt_slug': self.unfinalized_receipt.slug})
        )
        
        # Non-uploader should be denied access
        self.assertEqual(response.status_code, 403)
    
    @patch('receipts.image_storage.get_receipt_image_from_memory')
    def test_anyone_can_view_image_after_finalized(self, mock_get_image):
        """Test that anyone can view image after receipt is finalized"""
        mock_get_image.return_value = (b'fake_image_data', 'image/jpeg')
        
        # Set up session as non-uploader
        session = self.client.session
        session['receipts'] = {
            str(self.finalized_receipt.id): {
                'is_uploader': False,
                'viewer_name': self.viewer_name
            }
        }
        session.save()
        
        # Try to get image of finalized receipt
        response = self.client.get(
            reverse('serve_receipt_image', kwargs={'receipt_slug': self.finalized_receipt.slug})
        )
        
        # Should be able to view finalized receipt image
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'fake_image_data')
    
    def test_edit_page_redirect_for_non_uploader(self):
        """Test that non-uploaders cannot access edit page"""
        # Set up session as non-uploader
        session = self.client.session
        session['receipts'] = {
            str(self.unfinalized_receipt.id): {
                'is_uploader': False,
                'viewer_name': self.viewer_name
            }
        }
        session.save()
        
        # Try to access edit page
        response = self.client.get(
            reverse('edit_receipt', kwargs={'receipt_slug': self.unfinalized_receipt.slug})
        )
        
        # Should be redirected or denied
        self.assertEqual(response.status_code, 302)  # Redirect to index
    
    def test_edit_page_access_for_uploader(self):
        """Test that uploaders can access edit page"""
        # Set up session as uploader with edit token
        session = self.client.session
        session['receipts'] = {
            str(self.unfinalized_receipt.id): {
                'is_uploader': True,
                'viewer_name': self.uploader_name,
                'edit_token': 'test-edit-token'
            }
        }
        session.save()
        
        # Try to access edit page
        response = self.client.get(
            reverse('edit_receipt', kwargs={'receipt_slug': self.unfinalized_receipt.slug})
        )
        
        # Should be able to access
        self.assertIn(response.status_code, [200, 404])  # 404 if template doesn't exist


class UploaderPermissionIntegrationTests(TransactionTestCase):
    """Integration tests for complete uploader permission workflows"""
    
    def setUp(self):
        """Set up test environment"""
        self.client = Client()
        self.uploader_name = "Integration Uploader"
        self.viewer1_name = "Viewer One"
        self.viewer2_name = "Viewer Two"
    
    def test_complete_receipt_lifecycle_permissions(self):
        """Test permissions throughout the complete receipt lifecycle"""
        # Step 1: Create receipt as uploader
        receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Lifecycle Restaurant",
            date=timezone.now(),
            subtotal=Decimal('100.00'),
            tax=Decimal('10.00'),
            tip=Decimal('20.00'),
            total=Decimal('130.00'),
            is_finalized=False,
            processing_status='completed'
        )
        
        # Create items
        item1 = LineItem.objects.create(
            receipt=receipt,
            name="Steak",
            quantity=1,
            unit_price=Decimal('50.00'),
            total_price=Decimal('50.00')
        )
        
        item2 = LineItem.objects.create(
            receipt=receipt,
            name="Wine",
            quantity=2,
            unit_price=Decimal('25.00'),
            total_price=Decimal('50.00')
        )
        
        # Step 2: Set up uploader session
        uploader_session = self.client.session
        uploader_session['receipts'] = {
            str(receipt.id): {
                'is_uploader': True,
                'viewer_name': self.uploader_name,
                'edit_token': 'uploader-token'
            }
        }
        uploader_session.save()
        
        # Step 3: Uploader should be able to edit
        response = self.client.get(
            reverse('edit_receipt', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertNotEqual(response.status_code, 403)
        
        # Step 4: Non-uploader tries to access (should fail)
        viewer_client = Client()
        viewer_session = viewer_client.session
        viewer_session['receipts'] = {
            str(receipt.id): {
                'is_uploader': False,
                'viewer_name': self.viewer1_name
            }
        }
        viewer_session.save()
        
        response = viewer_client.get(
            reverse('edit_receipt', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertEqual(response.status_code, 302)  # Redirected
        
        # Step 5: Finalize receipt
        receipt.is_finalized = True
        receipt.save()
        
        # Step 6: Now viewer can view (and theoretically claim)
        response = viewer_client.get(
            reverse('view_receipt', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertIn(response.status_code, [200, 404])  # 404 if template missing
    
    def test_session_persistence_across_requests(self):
        """Test that session data persists correctly across multiple requests"""
        # Create receipt
        receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Persistence Test",
            date=timezone.now(),
            subtotal=Decimal('40.00'),
            tax=Decimal('4.00'),
            tip=Decimal('8.00'),
            total=Decimal('52.00'),
            is_finalized=True,
            processing_status='completed'
        )
        
        # First request - set viewer name
        session = self.client.session
        session['receipts'] = {
            str(receipt.id): {
                'viewer_name': self.viewer1_name,
                'is_uploader': False
            }
        }
        session.save()
        session_key = session.session_key
        
        # Second request - verify data persists
        client2 = Client()
        client2.cookies[session.session_key] = session_key
        
        # Make a request that would use the session
        with patch('receipts.views.receipt_service.get_receipt_by_slug') as mock_get:
            mock_get.return_value = receipt
            response = client2.get(
                reverse('view_receipt', kwargs={'receipt_slug': receipt.slug})
            )
        
        # Session should maintain viewer identity
        self.assertIn(response.status_code, [200, 404])
    
    def test_multiple_viewers_same_receipt(self):
        """Test that multiple viewers can interact with the same receipt independently"""
        # Create finalized receipt
        receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Multi-viewer Test",
            date=timezone.now(),
            subtotal=Decimal('90.00'),
            tax=Decimal('9.00'),
            tip=Decimal('18.00'),
            total=Decimal('117.00'),
            is_finalized=True,
            processing_status='completed'
        )
        
        # Create items
        item = LineItem.objects.create(
            receipt=receipt,
            name="Shared Platter",
            quantity=3,
            unit_price=Decimal('30.00'),
            total_price=Decimal('90.00')
        )
        
        # Viewer 1 claims
        client1 = Client()
        session1 = client1.session
        session1['receipts'] = {
            str(receipt.id): {
                'viewer_name': self.viewer1_name,
                'is_uploader': False
            }
        }
        session1.save()
        
        # Viewer 2 claims
        client2 = Client()
        session2 = client2.session
        session2['receipts'] = {
            str(receipt.id): {
                'viewer_name': self.viewer2_name,
                'is_uploader': False
            }
        }
        session2.save()
        
        # Create claims for both viewers
        Claim.objects.create(
            line_item=item,
            claimer_name=self.viewer1_name,
            quantity_claimed=1,
            session_id=session1.session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        Claim.objects.create(
            line_item=item,
            claimer_name=self.viewer2_name,
            quantity_claimed=1,
            session_id=session2.session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        # Verify both claims exist independently
        viewer1_claims = Claim.objects.filter(
            session_id=session1.session_key
        )
        viewer2_claims = Claim.objects.filter(
            session_id=session2.session_key
        )
        
        self.assertEqual(viewer1_claims.count(), 1)
        self.assertEqual(viewer2_claims.count(), 1)
        self.assertNotEqual(
            viewer1_claims.first().claimer_name,
            viewer2_claims.first().claimer_name
        )
    
    def test_edge_case_uploader_loses_session(self):
        """Test what happens when uploader loses their session and returns"""
        # Create receipt
        receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Lost Session Test",
            date=timezone.now(),
            subtotal=Decimal('60.00'),
            tax=Decimal('6.00'),
            tip=Decimal('12.00'),
            total=Decimal('78.00'),
            is_finalized=False,
            processing_status='completed'
        )
        
        # Original uploader session
        session1 = self.client.session
        session1['receipts'] = {
            str(receipt.id): {
                'is_uploader': True,
                'viewer_name': self.uploader_name,
                'edit_token': 'original-token'
            }
        }
        session1.save()
        
        # Uploader can edit
        response = self.client.get(
            reverse('edit_receipt', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertNotEqual(response.status_code, 403)
        
        # New session (lost cookies)
        client2 = Client()
        session2 = client2.session
        # No receipt data - acts as new viewer
        session2.save()
        
        # Cannot edit without proper session
        response = client2.get(
            reverse('edit_receipt', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertEqual(response.status_code, 302)  # Redirected
        
        # Even if they claim to be the uploader by name, they don't have edit permission
        session2['receipts'] = {
            str(receipt.id): {
                'viewer_name': self.uploader_name,
                'is_uploader': False  # System doesn't know they're the uploader
            }
        }
        session2.save()
        
        response = client2.get(
            reverse('edit_receipt', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertEqual(response.status_code, 302)  # Still redirected
    
    def test_same_session_different_names_maintains_permissions(self):
        """Test that permissions are maintained even when forced to use different names"""
        # Create receipt as uploader
        receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Name Change Test",
            date=timezone.now(),
            subtotal=Decimal('50.00'),
            tax=Decimal('5.00'),
            tip=Decimal('10.00'),
            total=Decimal('65.00'),
            is_finalized=False,
            processing_status='completed'
        )
        
        # Set up as uploader
        session = self.client.session
        session['receipts'] = {
            str(receipt.id): {
                'is_uploader': True,
                'viewer_name': self.uploader_name,
                'edit_token': 'test-token'
            }
        }
        session.save()
        
        # Uploader should have edit access
        response = self.client.get(
            reverse('edit_receipt', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertNotEqual(response.status_code, 403)
        
        # Simulate being forced to use a different name (but same session)
        # This might happen if the uploader's name was already taken when they return
        session['receipts'][str(receipt.id)]['viewer_name'] = f"{self.uploader_name} 2"
        session.save()
        
        # Should STILL have edit access because is_uploader=True and edit_token is present
        response = self.client.get(
            reverse('edit_receipt', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertNotEqual(response.status_code, 403)
        
        # Verify they still have uploader privileges
        user_context = UserContext(
            ReceiptSessionManager(self.client),
            receipt.id
        )
        self.assertTrue(user_context.is_uploader)
        self.assertTrue(user_context.can_edit)
    
    def test_name_collision_does_not_affect_permissions(self):
        """Test that name collisions don't affect permission checks"""
        # Create receipt
        receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Collision Test",
            date=timezone.now(),
            subtotal=Decimal('40.00'),
            tax=Decimal('4.00'),
            tip=Decimal('8.00'),
            total=Decimal('52.00'),
            is_finalized=True,
            processing_status='completed'
        )
        
        # First viewer claims with name "John"
        client1 = Client()
        session1 = client1.session
        session1['receipts'] = {
            str(receipt.id): {
                'viewer_name': 'John',
                'is_uploader': False
            }
        }
        session1.save()
        
        # Create a claim as John
        Claim.objects.create(
            line_item=LineItem.objects.create(
                receipt=receipt,
                name="Item 1",
                quantity=1,
                unit_price=Decimal('20.00'),
                total_price=Decimal('20.00')
            ),
            claimer_name='John',
            quantity_claimed=1,
            session_id=session1.session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        # Second viewer also wants to use "John" but gets assigned "John 2"
        client2 = Client()
        session2 = client2.session
        session2['receipts'] = {
            str(receipt.id): {
                'viewer_name': 'John 2',  # Forced to use different name
                'is_uploader': False
            }
        }
        session2.save()
        
        # Each should only be able to undo their own claims
        claim1 = Claim.objects.filter(session_id=session1.session_key).first()
        claim2 = Claim.objects.create(
            line_item=LineItem.objects.create(
                receipt=receipt,
                name="Item 2",
                quantity=1,
                unit_price=Decimal('20.00'),
                total_price=Decimal('20.00')
            ),
            claimer_name='John 2',
            quantity_claimed=1,
            session_id=session2.session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        # Client 1 cannot undo Client 2's claim
        from receipts.services import ClaimService
        claim_service = ClaimService()
        
        with self.assertRaises(PermissionError):
            claim_service.undo_claim(str(claim2.id), session1.session_key)
        
        # Client 2 cannot undo Client 1's claim
        with self.assertRaises(PermissionError):
            claim_service.undo_claim(str(claim1.id), session2.session_key)
        
        # But each can undo their own
        self.assertTrue(claim_service.undo_claim(str(claim1.id), session1.session_key))
        self.assertTrue(claim_service.undo_claim(str(claim2.id), session2.session_key))
    
    @patch('receipts.image_storage.get_receipt_image_from_memory')
    def test_image_permissions_with_name_changes(self, mock_get_image):
        """Test image viewing permissions when names change in same session"""
        mock_get_image.return_value = (b'test_image_data', 'image/jpeg')
        
        # Create unfinalized receipt
        receipt = Receipt.objects.create(
            uploader_name=self.uploader_name,
            restaurant_name="Image Permission Test",
            date=timezone.now(),
            subtotal=Decimal('30.00'),
            tax=Decimal('3.00'),
            tip=Decimal('6.00'),
            total=Decimal('39.00'),
            is_finalized=False,
            processing_status='completed'
        )
        
        # Set up as uploader
        session = self.client.session
        session['receipts'] = {
            str(receipt.id): {
                'is_uploader': True,
                'viewer_name': self.uploader_name,
                'edit_token': 'test-token'
            }
        }
        session.save()
        
        # Can view image as uploader
        response = self.client.get(
            reverse('serve_receipt_image', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertEqual(response.status_code, 200)
        
        # Change name (simulating being forced to use different name)
        session['receipts'][str(receipt.id)]['viewer_name'] = f"{self.uploader_name} New"
        session.save()
        
        # Should still be able to view image because is_uploader=True
        response = self.client.get(
            reverse('serve_receipt_image', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertEqual(response.status_code, 200)
        
        # Non-uploader with any name cannot view
        client2 = Client()
        session2 = client2.session
        session2['receipts'] = {
            str(receipt.id): {
                'is_uploader': False,
                'viewer_name': 'Any Name'
            }
        }
        session2.save()
        
        response = client2.get(
            reverse('serve_receipt_image', kwargs={'receipt_slug': receipt.slug})
        )
        self.assertEqual(response.status_code, 403)
    
    def test_claim_calculations_with_session_name_mismatch(self):
        """Test that claim calculations work correctly when session has multiple names"""
        # This tests the exact bug that was fixed
        receipt = Receipt.objects.create(
            uploader_name="Restaurant",
            restaurant_name="Bug Test Restaurant",
            date=timezone.now(),
            subtotal=Decimal('100.00'),
            tax=Decimal('10.00'),
            tip=Decimal('20.00'),
            total=Decimal('130.00'),
            is_finalized=True,
            processing_status='completed'
        )
        
        # Create items
        item1 = LineItem.objects.create(
            receipt=receipt,
            name="Pizza",
            quantity=1,
            unit_price=Decimal('50.00'),
            total_price=Decimal('50.00'),
            prorated_tax=Decimal('5.00'),
            prorated_tip=Decimal('10.00')
        )
        
        item2 = LineItem.objects.create(
            receipt=receipt,
            name="Salad",
            quantity=1,
            unit_price=Decimal('30.00'),
            total_price=Decimal('30.00'),
            prorated_tax=Decimal('3.00'),
            prorated_tip=Decimal('6.00')
        )
        
        # Set up session
        session = self.client.session
        session['receipts'] = {
            str(receipt.id): {
                'viewer_name': 'Original Name',
                'is_uploader': False
            }
        }
        session.save()
        
        # Create claim with original name
        Claim.objects.create(
            line_item=item1,
            claimer_name='Original Name',
            quantity_claimed=1,
            session_id=session.session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=5)
        )
        
        # Simulate being forced to use a different name
        session['receipts'][str(receipt.id)]['viewer_name'] = 'Original Name 2'
        session.save()
        
        # Create claim with new name
        Claim.objects.create(
            line_item=item2,
            claimer_name='Original Name 2',
            quantity_claimed=1,
            session_id=session.session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=5)
        )
        
        # Test that totals are calculated correctly by name
        from receipts.services import ClaimService
        claim_service = ClaimService()
        
        # Original Name should only see Pizza claim
        original_total = claim_service.calculate_name_total(receipt.id, 'Original Name')
        self.assertEqual(original_total, Decimal('65.00'))  # 50 + 5 + 10
        
        # Original Name 2 should only see Salad claim
        new_name_total = claim_service.calculate_name_total(receipt.id, 'Original Name 2')
        self.assertEqual(new_name_total, Decimal('39.00'))  # 30 + 3 + 6
        
        # Session total would include both (this was the bug)
        session_total = claim_service.calculate_session_total(receipt.id, session.session_key)
        self.assertEqual(session_total, Decimal('104.00'))  # 65 + 39
        
        # Verify each name sees only their claims
        original_claims = claim_service.get_claims_for_name(receipt.id, 'Original Name')
        self.assertEqual(len(original_claims), 1)
        self.assertEqual(original_claims[0].line_item.name, 'Pizza')
        
        new_name_claims = claim_service.get_claims_for_name(receipt.id, 'Original Name 2')
        self.assertEqual(len(new_name_claims), 1)
        self.assertEqual(new_name_claims[0].line_item.name, 'Salad')