"""
Unit tests for ReceiptSessionManager.
"""

from datetime import datetime, timedelta
from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils import timezone
from unittest.mock import Mock, patch

from ..session_manager import ReceiptSessionManager


class ReceiptSessionManagerTest(TestCase):
    
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        
        # Add session support
        middleware = SessionMiddleware(lambda x: x)
        middleware.process_request(self.request)
        self.request.session.save()
        
        self.session_manager = ReceiptSessionManager(self.request)
        self.receipt_id = 'test-receipt-123'
    
    def test_init_creates_session_if_needed(self):
        """Test that ReceiptSessionManager ensures session exists"""
        # Create request without session
        request = self.factory.get('/')
        middleware = SessionMiddleware(lambda x: x)
        middleware.process_request(request)
        
        # Session key should not exist yet
        self.assertIsNone(request.session.session_key)
        
        # Creating session manager should create session
        session_manager = ReceiptSessionManager(request)
        self.assertIsNotNone(request.session.session_key)
    
    def test_session_id_property(self):
        """Test session_id property returns correct session key"""
        self.assertEqual(self.session_manager.session_id, self.request.session.session_key)
    
    def test_viewer_identity_management(self):
        """Test setting and getting viewer identity"""
        # Initially no viewer identity
        self.assertIsNone(self.session_manager.get_viewer_identity(self.receipt_id))
        
        # Set viewer identity
        self.session_manager.set_viewer_identity(self.receipt_id, 'Alice')
        self.assertEqual(self.session_manager.get_viewer_identity(self.receipt_id), 'Alice')
        
        # Verify viewed_at timestamp was set
        data = self.session_manager._get_receipt_data(self.receipt_id)
        self.assertIn('viewed_at', data)
    
    def test_edit_token_management(self):
        """Test edit token creation and retrieval"""
        # Initially no edit token
        self.assertIsNone(self.session_manager.get_edit_token(self.receipt_id))
        
        # Grant edit permission
        token = self.session_manager.grant_edit_permission(self.receipt_id)
        self.assertIsNotNone(token)
        self.assertEqual(len(token), 43)  # token_urlsafe(32) creates 43-char string
        
        # Retrieve token
        self.assertEqual(self.session_manager.get_edit_token(self.receipt_id), token)
        
        # Verify granted_at timestamp was set
        data = self.session_manager._get_receipt_data(self.receipt_id)
        self.assertIn('granted_at', data)
    
    def test_revoke_edit_permission(self):
        """Test revoking edit permission"""
        # Grant permission first
        token = self.session_manager.grant_edit_permission(self.receipt_id)
        self.assertIsNotNone(self.session_manager.get_edit_token(self.receipt_id))
        
        # Revoke permission
        self.session_manager.revoke_edit_permission(self.receipt_id)
        self.assertIsNone(self.session_manager.get_edit_token(self.receipt_id))
        
        # Verify timestamps were removed
        data = self.session_manager._get_receipt_data(self.receipt_id)
        self.assertNotIn('edit_token', data)
        self.assertNotIn('granted_at', data)
    
    def test_uploader_management(self):
        """Test uploader status management"""
        # Initially not uploader
        self.assertFalse(self.session_manager.is_uploader(self.receipt_id))
        
        # Mark as uploader
        self.session_manager.mark_as_uploader(self.receipt_id)
        self.assertTrue(self.session_manager.is_uploader(self.receipt_id))
        
        # Verify uploaded_at timestamp was set
        data = self.session_manager._get_receipt_data(self.receipt_id)
        self.assertIn('uploaded_at', data)
    
    def test_session_context_creation(self):
        """Test session context for service layer compatibility"""
        # Set up some data
        self.session_manager.set_viewer_identity(self.receipt_id, 'Bob')
        self.session_manager.mark_as_uploader(self.receipt_id)
        token = self.session_manager.grant_edit_permission(self.receipt_id)
        
        # Get session context
        context = self.session_manager.get_session_context(self.receipt_id)
        
        self.assertEqual(context['receipt_id'], str(self.receipt_id))
        self.assertEqual(context['session_key'], self.request.session.session_key)
        self.assertEqual(context['edit_token'], token)
        self.assertTrue(context['is_uploader'])
        self.assertEqual(context['viewer_name'], 'Bob')
    
    def test_namespace_isolation(self):
        """Test that receipt data is properly namespaced"""
        self.session_manager.set_viewer_identity(self.receipt_id, 'Alice')
        
        # Check session structure
        self.assertIn(ReceiptSessionManager.NAMESPACE, self.request.session)
        namespace = self.request.session[ReceiptSessionManager.NAMESPACE]
        self.assertIn(str(self.receipt_id), namespace)
        self.assertEqual(namespace[str(self.receipt_id)]['viewer_name'], 'Alice')
    
    def test_multiple_receipts(self):
        """Test managing multiple receipts in same session"""
        receipt_id_1 = 'receipt-1'
        receipt_id_2 = 'receipt-2'
        
        # Set different data for each receipt
        self.session_manager.set_viewer_identity(receipt_id_1, 'Alice')
        self.session_manager.set_viewer_identity(receipt_id_2, 'Bob')
        self.session_manager.mark_as_uploader(receipt_id_1)
        
        # Verify isolation
        self.assertEqual(self.session_manager.get_viewer_identity(receipt_id_1), 'Alice')
        self.assertEqual(self.session_manager.get_viewer_identity(receipt_id_2), 'Bob')
        self.assertTrue(self.session_manager.is_uploader(receipt_id_1))
        self.assertFalse(self.session_manager.is_uploader(receipt_id_2))
    
    def test_cleanup_old_receipts(self):
        """Test cleanup of old receipt data"""
        now = timezone.now()
        
        # Create old receipt data (8 days ago)
        old_time = now - timedelta(days=8)
        self.session_manager.set_viewer_identity('old-receipt', 'Alice')
        
        # Manually set old timestamp
        namespace = self.request.session[ReceiptSessionManager.NAMESPACE]
        namespace['old-receipt']['viewed_at'] = old_time.isoformat()
        self.request.session.modified = True
        
        # Create recent receipt data (2 days ago)  
        recent_time = now - timedelta(days=2)
        self.session_manager.set_viewer_identity('recent-receipt', 'Bob')
        namespace['recent-receipt']['viewed_at'] = recent_time.isoformat()
        self.request.session.modified = True
        
        # Run cleanup (default 7 days)
        cleaned_count = self.session_manager.cleanup_old_receipts()
        
        # Verify old data was cleaned
        self.assertEqual(cleaned_count, 1)
        self.assertIsNone(self.session_manager.get_viewer_identity('old-receipt'))
        self.assertEqual(self.session_manager.get_viewer_identity('recent-receipt'), 'Bob')
    
    def test_cleanup_uses_most_recent_timestamp(self):
        """Test that cleanup uses the most recent of viewed_at or uploaded_at"""
        now = timezone.now()
        old_viewed = now - timedelta(days=8)
        recent_uploaded = now - timedelta(days=2)
        
        # Set old viewed_at but recent uploaded_at
        self.session_manager.set_viewer_identity(self.receipt_id, 'Alice')
        namespace = self.request.session[ReceiptSessionManager.NAMESPACE]
        namespace[str(self.receipt_id)]['viewed_at'] = old_viewed.isoformat()
        namespace[str(self.receipt_id)]['uploaded_at'] = recent_uploaded.isoformat()
        self.request.session.modified = True
        
        # Run cleanup
        cleaned_count = self.session_manager.cleanup_old_receipts()
        
        # Should not be cleaned because uploaded_at is recent
        self.assertEqual(cleaned_count, 0)
        self.assertEqual(self.session_manager.get_viewer_identity(self.receipt_id), 'Alice')
    
    def test_get_all_receipt_data(self):
        """Test getting all receipt data for debugging"""
        self.session_manager.set_viewer_identity('receipt-1', 'Alice')
        self.session_manager.set_viewer_identity('receipt-2', 'Bob')
        
        all_data = self.session_manager.get_all_receipt_data()
        self.assertIn('receipt-1', all_data)
        self.assertIn('receipt-2', all_data)
        self.assertEqual(all_data['receipt-1']['viewer_name'], 'Alice')
        self.assertEqual(all_data['receipt-2']['viewer_name'], 'Bob')
    
    def test_clear_receipt_data(self):
        """Test clearing data for specific receipt"""
        # Set up data for multiple receipts
        self.session_manager.set_viewer_identity('receipt-1', 'Alice')
        self.session_manager.set_viewer_identity('receipt-2', 'Bob')
        
        # Clear one receipt
        self.session_manager.clear_receipt_data('receipt-1')
        
        # Verify only one was cleared
        self.assertIsNone(self.session_manager.get_viewer_identity('receipt-1'))
        self.assertEqual(self.session_manager.get_viewer_identity('receipt-2'), 'Bob')
    
    def test_session_modified_flag(self):
        """Test that session.modified is set when data changes"""
        # Reset modified flag
        self.request.session.modified = False
        
        # Modify data
        self.session_manager.set_viewer_identity(self.receipt_id, 'Alice')
        
        # Verify session was marked as modified
        self.assertTrue(self.request.session.modified)
    
    def test_handles_missing_session(self):
        """Test graceful handling when session is not available"""
        # Create request with session that doesn't have session_key
        request = Mock()
        request.session = Mock()
        request.session.session_key = None
        request.session.get = Mock(return_value={})
        request.session.__contains__ = Mock(return_value=False)
        request.session.__getitem__ = Mock(side_effect=KeyError())
        request.session.__setitem__ = Mock()
        request.session.save = Mock()
        
        session_manager = ReceiptSessionManager(request)
        
        # Should not crash and return empty data
        self.assertEqual(session_manager._get_receipt_data(self.receipt_id), {})
        self.assertIsNone(session_manager.get_viewer_identity(self.receipt_id))
        
        # Cleanup should return 0
        self.assertEqual(session_manager.cleanup_old_receipts(), 0)