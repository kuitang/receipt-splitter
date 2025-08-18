"""
Session management for receipt-related functionality.
Provides a clean abstraction over Django sessions for receipt operations.
"""

import secrets
from datetime import datetime, timedelta
from django.utils import timezone


class ReceiptSessionManager:
    """Manages all receipt-related session data with proper namespacing"""
    
    NAMESPACE = 'receipts'
    
    def __init__(self, request):
        self.request = request
        self._ensure_session()
    
    def _ensure_session(self):
        """Ensure session exists without forcing creation unnecessarily"""
        if not hasattr(self.request, 'session'):
            return
        if not self.request.session.session_key:
            self.request.session.save()
    
    @property
    def session_id(self):
        """Get the current session ID"""
        return self.request.session.session_key
    
    def get_viewer_identity(self, receipt_id):
        """Get viewer identity for a specific receipt"""
        data = self._get_receipt_data(receipt_id)
        viewer_name = data.get('viewer_name')
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"[SessionManager.get_viewer_identity] receipt_id={receipt_id}, session_id={self.session_id}, viewer_name={viewer_name}, full_data={data}")
        
        return viewer_name
    
    def set_viewer_identity(self, receipt_id, name):
        """Set viewer identity for a receipt"""
        data = self._get_receipt_data(receipt_id)
        data['viewer_name'] = name
        data['viewed_at'] = timezone.now().isoformat()
        self._save_receipt_data(receipt_id, data)
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"[SessionManager.set_viewer_identity] receipt_id={receipt_id}, session_id={self.session_id}, name={name}, saved_data={data}")
    
    def get_edit_token(self, receipt_id):
        """Get edit token for a receipt"""
        data = self._get_receipt_data(receipt_id)
        return data.get('edit_token')
    
    def grant_edit_permission(self, receipt_id):
        """Grant edit permission for a receipt"""
        token = secrets.token_urlsafe(32)
        data = self._get_receipt_data(receipt_id)
        data['edit_token'] = token
        data['granted_at'] = timezone.now().isoformat()
        self._save_receipt_data(receipt_id, data)
        return token
    
    def revoke_edit_permission(self, receipt_id):
        """Revoke edit permission for a receipt"""
        data = self._get_receipt_data(receipt_id)
        if 'edit_token' in data:
            del data['edit_token']
        if 'granted_at' in data:
            del data['granted_at']
        self._save_receipt_data(receipt_id, data)
    
    def is_uploader(self, receipt_id):
        """Check if current session uploaded this receipt"""
        data = self._get_receipt_data(receipt_id)
        return data.get('is_uploader', False)
    
    def mark_as_uploader(self, receipt_id):
        """Mark current session as uploader of receipt"""
        data = self._get_receipt_data(receipt_id)
        data['is_uploader'] = True
        data['uploaded_at'] = timezone.now().isoformat()
        self._save_receipt_data(receipt_id, data)
    
    def get_session_context(self, receipt_id):
        """Get session context for service layer compatibility"""
        data = self._get_receipt_data(receipt_id)
        return {
            'receipt_id': str(receipt_id),
            'session_key': self.session_id,
            'edit_token': data.get('edit_token'),
            'is_uploader': data.get('is_uploader', False),
            'viewer_name': data.get('viewer_name')
        }
    
    def _get_receipt_data(self, receipt_id):
        """Get all session data for a receipt"""
        if not hasattr(self.request, 'session'):
            return {}
        namespace = self.request.session.get(self.NAMESPACE, {})
        return namespace.get(str(receipt_id), {})
    
    def _save_receipt_data(self, receipt_id, data):
        """Save receipt data to session"""
        if not hasattr(self.request, 'session'):
            return
        if self.NAMESPACE not in self.request.session:
            self.request.session[self.NAMESPACE] = {}
        self.request.session[self.NAMESPACE][str(receipt_id)] = data
        self.request.session.modified = True
    
    def cleanup_old_receipts(self, days=7):
        """Remove receipt data older than specified days"""
        if not hasattr(self.request, 'session'):
            return 0
        if self.NAMESPACE not in self.request.session:
            return 0
        
        cutoff = timezone.now() - timedelta(days=days)
        namespace = self.request.session[self.NAMESPACE]
        cleaned_count = 0
        
        for receipt_id in list(namespace.keys()):
            data = namespace[receipt_id]
            viewed_at = data.get('viewed_at')
            uploaded_at = data.get('uploaded_at')
            
            # Use the most recent timestamp
            most_recent = None
            if viewed_at:
                try:
                    if isinstance(viewed_at, str):
                        most_recent = datetime.fromisoformat(viewed_at.replace('Z', '+00:00'))
                    else:
                        most_recent = viewed_at
                except (ValueError, TypeError):
                    pass
            if uploaded_at:
                try:
                    if isinstance(uploaded_at, str):
                        uploaded_time = datetime.fromisoformat(uploaded_at.replace('Z', '+00:00'))
                    else:
                        uploaded_time = uploaded_at
                    if most_recent is None or uploaded_time > most_recent:
                        most_recent = uploaded_time
                except (ValueError, TypeError):
                    pass
            
            if most_recent and most_recent < cutoff:
                del namespace[receipt_id]
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.request.session.modified = True
        
        return cleaned_count
    
    def get_all_receipt_data(self):
        """Get all receipt data (for debugging/testing)"""
        if not hasattr(self.request, 'session'):
            return {}
        return self.request.session.get(self.NAMESPACE, {})
    
    def clear_receipt_data(self, receipt_id):
        """Clear all data for a specific receipt"""
        if not hasattr(self.request, 'session'):
            return
        if self.NAMESPACE not in self.request.session:
            return
        
        namespace = self.request.session[self.NAMESPACE]
        if str(receipt_id) in namespace:
            del namespace[str(receipt_id)]
            self.request.session.modified = True