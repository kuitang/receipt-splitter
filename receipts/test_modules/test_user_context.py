"""
Unit tests for UserContext.
"""

from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from unittest.mock import Mock

from ..session_manager import ReceiptSessionManager
from ..user_context import UserContext


class UserContextTest(TestCase):
    
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        
        # Add session support
        middleware = SessionMiddleware(lambda x: x)
        middleware.process_request(self.request)
        self.request.session.save()
        
        self.session_manager = ReceiptSessionManager(self.request)
        self.receipt_id = 'test-receipt-123'
        self.user_context = UserContext(self.session_manager, self.receipt_id)
    
    def test_session_id_property(self):
        """Test session_id property delegates to session manager"""
        self.assertEqual(self.user_context.session_id, self.session_manager.session_id)
    
    def test_name_property_with_receipt(self):
        """Test name property when receipt_id is set"""
        # Initially no name
        self.assertIsNone(self.user_context.name)
        
        # Set name through session manager
        self.session_manager.set_viewer_identity(self.receipt_id, 'Alice')
        
        # Should return name through context
        self.assertEqual(self.user_context.name, 'Alice')
    
    def test_name_property_without_receipt(self):
        """Test name property when no receipt_id is set"""
        context = UserContext(self.session_manager)
        self.assertIsNone(context.name)
    
    def test_can_edit_property(self):
        """Test can_edit property logic"""
        # Initially cannot edit
        self.assertFalse(self.user_context.can_edit)
        
        # Grant edit token
        self.session_manager.grant_edit_permission(self.receipt_id)
        self.assertTrue(self.user_context.can_edit)
        
        # Revoke token
        self.session_manager.revoke_edit_permission(self.receipt_id)
        self.assertFalse(self.user_context.can_edit)
        
        # Mark as uploader (should allow edit)
        self.session_manager.mark_as_uploader(self.receipt_id)
        self.assertTrue(self.user_context.can_edit)
    
    def test_can_edit_without_receipt(self):
        """Test can_edit when no receipt_id is set"""
        context = UserContext(self.session_manager)
        self.assertFalse(context.can_edit)
    
    def test_is_uploader_property(self):
        """Test is_uploader property"""
        # Initially not uploader
        self.assertFalse(self.user_context.is_uploader)
        
        # Mark as uploader
        self.session_manager.mark_as_uploader(self.receipt_id)
        self.assertTrue(self.user_context.is_uploader)
    
    def test_is_uploader_without_receipt(self):
        """Test is_uploader when no receipt_id is set"""
        context = UserContext(self.session_manager)
        self.assertFalse(context.is_uploader)
    
    def test_is_authenticated_property(self):
        """Test is_authenticated property"""
        # Initially not authenticated
        self.assertFalse(self.user_context.is_authenticated)
        
        # Set name
        self.session_manager.set_viewer_identity(self.receipt_id, 'Alice')
        self.assertTrue(self.user_context.is_authenticated)
    
    def test_edit_token_property(self):
        """Test edit_token property"""
        # Initially no token
        self.assertIsNone(self.user_context.edit_token)
        
        # Grant permission
        token = self.session_manager.grant_edit_permission(self.receipt_id)
        self.assertEqual(self.user_context.edit_token, token)
    
    def test_edit_token_without_receipt(self):
        """Test edit_token when no receipt_id is set"""
        context = UserContext(self.session_manager)
        self.assertIsNone(context.edit_token)
    
    def test_authenticate_as(self):
        """Test authenticate_as method"""
        self.user_context.authenticate_as('Bob')
        self.assertEqual(self.user_context.name, 'Bob')
        self.assertTrue(self.user_context.is_authenticated)
    
    def test_authenticate_as_without_receipt(self):
        """Test authenticate_as when no receipt_id is set"""
        context = UserContext(self.session_manager)
        context.authenticate_as('Bob')
        # Should not crash, but no effect
        self.assertIsNone(context.name)
    
    def test_grant_edit_permission(self):
        """Test grant_edit_permission method"""
        token = self.user_context.grant_edit_permission()
        self.assertIsNotNone(token)
        self.assertEqual(self.user_context.edit_token, token)
        self.assertTrue(self.user_context.can_edit)
    
    def test_grant_edit_permission_without_receipt(self):
        """Test grant_edit_permission when no receipt_id is set"""
        context = UserContext(self.session_manager)
        token = context.grant_edit_permission()
        self.assertIsNone(token)
    
    def test_revoke_edit_permission(self):
        """Test revoke_edit_permission method"""
        # Grant first
        self.user_context.grant_edit_permission()
        self.assertTrue(self.user_context.can_edit)
        
        # Revoke
        self.user_context.revoke_edit_permission()
        self.assertFalse(self.user_context.can_edit)
        self.assertIsNone(self.user_context.edit_token)
    
    def test_mark_as_uploader(self):
        """Test mark_as_uploader method"""
        self.user_context.mark_as_uploader()
        self.assertTrue(self.user_context.is_uploader)
        self.assertTrue(self.user_context.can_edit)
    
    def test_get_session_context_with_receipt(self):
        """Test get_session_context method with receipt"""
        # Set up some data
        self.user_context.authenticate_as('Charlie')
        self.user_context.mark_as_uploader()
        token = self.user_context.grant_edit_permission()
        
        context = self.user_context.get_session_context()
        
        self.assertEqual(context['receipt_id'], str(self.receipt_id))
        self.assertEqual(context['session_key'], self.session_manager.session_id)
        self.assertEqual(context['edit_token'], token)
        self.assertTrue(context['is_uploader'])
        self.assertEqual(context['viewer_name'], 'Charlie')
    
    def test_get_session_context_without_receipt(self):
        """Test get_session_context method without receipt"""
        context = UserContext(self.session_manager)
        session_context = context.get_session_context()
        
        self.assertEqual(session_context['session_key'], self.session_manager.session_id)
        self.assertNotIn('receipt_id', session_context)
    
    def test_with_receipt(self):
        """Test with_receipt method creates new context"""
        new_receipt_id = 'new-receipt-456'
        new_context = self.user_context.with_receipt(new_receipt_id)
        
        # Should be different instance
        self.assertIsNot(new_context, self.user_context)
        
        # Should share same session manager
        self.assertIs(new_context.session_manager, self.user_context.session_manager)
        
        # Should have new receipt_id
        self.assertEqual(new_context.receipt_id, new_receipt_id)
        self.assertEqual(self.user_context.receipt_id, self.receipt_id)
    
    def test_context_isolation(self):
        """Test that different contexts for different receipts are isolated"""
        receipt_id_1 = 'receipt-1'
        receipt_id_2 = 'receipt-2'
        
        context_1 = UserContext(self.session_manager, receipt_id_1)
        context_2 = UserContext(self.session_manager, receipt_id_2)
        
        # Set different data for each
        context_1.authenticate_as('Alice')
        context_1.mark_as_uploader()
        
        context_2.authenticate_as('Bob')
        
        # Verify isolation
        self.assertEqual(context_1.name, 'Alice')
        self.assertEqual(context_2.name, 'Bob')
        self.assertTrue(context_1.is_uploader)
        self.assertFalse(context_2.is_uploader)
        self.assertTrue(context_1.can_edit)
        self.assertFalse(context_2.can_edit)