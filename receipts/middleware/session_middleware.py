"""
Middleware for managing receipt sessions.
Provides session management and cleanup functionality.
"""

import random
from ..session_manager import ReceiptSessionManager
from ..user_context import UserContext


class ReceiptSessionMiddleware:
    """Middleware to manage receipt sessions and provide context"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Attach session manager to request
        request.receipt_session = ReceiptSessionManager(request)
        
        # Attach user context factory to request
        request.user_context = lambda receipt_id=None: UserContext(
            request.receipt_session, receipt_id
        )
        
        # Cleanup old data periodically (1% chance to avoid overhead)
        if random.random() < 0.01:
            try:
                cleaned_count = request.receipt_session.cleanup_old_receipts()
                if cleaned_count > 0:
                    # Could log this for monitoring
                    pass
            except Exception:
                # Don't let cleanup failures break the request
                pass
        
        response = self.get_response(request)
        return response