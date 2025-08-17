"""
Unit tests for ReceiptSessionMiddleware.
"""

from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from unittest.mock import Mock, patch

from ..middleware.session_middleware import ReceiptSessionMiddleware
from ..session_manager import ReceiptSessionManager
from ..user_context import UserContext


class ReceiptSessionMiddlewareTest(TestCase):
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ReceiptSessionMiddleware(lambda request: Mock())
    
    def test_middleware_attaches_session_manager(self):
        """Test that middleware attaches session manager to request"""
        request = self.factory.get('/')
        
        # Add session support
        session_middleware = SessionMiddleware(lambda x: x)
        session_middleware.process_request(request)
        request.session.save()
        
        # Process with our middleware
        self.middleware(request)
        
        # Verify session manager was attached
        self.assertIsInstance(request.receipt_session, ReceiptSessionManager)
        self.assertEqual(request.receipt_session.request, request)
    
    def test_middleware_attaches_user_context_factory(self):
        """Test that middleware attaches user context factory to request"""
        request = self.factory.get('/')
        
        # Add session support
        session_middleware = SessionMiddleware(lambda x: x)
        session_middleware.process_request(request)
        request.session.save()
        
        # Process with our middleware
        self.middleware(request)
        
        # Verify user context factory was attached
        self.assertTrue(callable(request.user_context))
        
        # Test factory without receipt_id
        context = request.user_context()
        self.assertIsInstance(context, UserContext)
        self.assertIsNone(context.receipt_id)
        
        # Test factory with receipt_id
        context = request.user_context('test-receipt')
        self.assertIsInstance(context, UserContext)
        self.assertEqual(context.receipt_id, 'test-receipt')
    
    @patch('receipts.middleware.session_middleware.random.random')
    def test_cleanup_happens_randomly(self, mock_random):
        """Test that cleanup happens 1% of the time"""
        request = self.factory.get('/')
        
        # Add session support
        session_middleware = SessionMiddleware(lambda x: x)
        session_middleware.process_request(request)
        request.session.save()
        
        # Mock random to return value that should trigger cleanup
        mock_random.return_value = 0.005  # Less than 0.01
        
        with patch.object(ReceiptSessionManager, 'cleanup_old_receipts') as mock_cleanup:
            mock_cleanup.return_value = 0
            self.middleware(request)
            mock_cleanup.assert_called_once()
        
        # Reset and test value that should not trigger cleanup
        mock_random.return_value = 0.02  # Greater than 0.01
        
        with patch.object(ReceiptSessionManager, 'cleanup_old_receipts') as mock_cleanup:
            self.middleware(request)
            mock_cleanup.assert_not_called()
    
    @patch('receipts.middleware.session_middleware.random.random')
    def test_cleanup_exception_handling(self, mock_random):
        """Test that cleanup exceptions don't break the request"""
        request = self.factory.get('/')
        
        # Add session support
        session_middleware = SessionMiddleware(lambda x: x)
        session_middleware.process_request(request)
        request.session.save()
        
        # Mock random to trigger cleanup
        mock_random.return_value = 0.005
        
        # Mock cleanup to raise exception
        with patch.object(ReceiptSessionManager, 'cleanup_old_receipts') as mock_cleanup:
            mock_cleanup.side_effect = Exception("Cleanup failed")
            
            # Should not raise exception
            try:
                response = self.middleware(request)
                self.assertIsNotNone(response)
            except Exception as e:
                self.fail(f"Middleware raised exception: {e}")
    
    def test_get_response_is_called(self):
        """Test that the get_response callable is invoked"""
        request = self.factory.get('/')
        expected_response = Mock()
        
        # Create middleware with mock get_response
        get_response = Mock(return_value=expected_response)
        middleware = ReceiptSessionMiddleware(get_response)
        
        # Add session support
        session_middleware = SessionMiddleware(lambda x: x)
        session_middleware.process_request(request)
        request.session.save()
        
        # Process request
        response = middleware(request)
        
        # Verify get_response was called with request
        get_response.assert_called_once_with(request)
        self.assertEqual(response, expected_response)