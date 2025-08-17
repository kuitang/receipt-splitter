"""
User context abstraction for receipt operations.
Provides a clean interface for user identity and permissions.
"""


class UserContext:
    """Represents the current user's context for receipt operations"""
    
    def __init__(self, session_manager, receipt_id=None):
        self.session_manager = session_manager
        self.receipt_id = receipt_id
    
    @property
    def session_id(self):
        """Get the current session ID"""
        return self.session_manager.session_id
    
    @property
    def name(self):
        """Get user's name for current receipt"""
        if self.receipt_id:
            return self.session_manager.get_viewer_identity(self.receipt_id)
        return None
    
    @property
    def can_edit(self):
        """Check if user can edit current receipt"""
        if not self.receipt_id:
            return False
        return (self.session_manager.is_uploader(self.receipt_id) or
                bool(self.session_manager.get_edit_token(self.receipt_id)))
    
    @property
    def is_uploader(self):
        """Check if user is the uploader of current receipt"""
        if not self.receipt_id:
            return False
        return self.session_manager.is_uploader(self.receipt_id)
    
    @property
    def is_authenticated(self):
        """Check if user has established identity for current receipt"""
        return self.name is not None
    
    @property
    def edit_token(self):
        """Get the edit token for current receipt"""
        if not self.receipt_id:
            return None
        return self.session_manager.get_edit_token(self.receipt_id)
    
    def authenticate_as(self, name):
        """Set user identity for current receipt"""
        if self.receipt_id:
            self.session_manager.set_viewer_identity(self.receipt_id, name)
    
    def grant_edit_permission(self):
        """Grant edit permission to current user for current receipt"""
        if self.receipt_id:
            return self.session_manager.grant_edit_permission(self.receipt_id)
        return None
    
    def revoke_edit_permission(self):
        """Revoke edit permission for current receipt"""
        if self.receipt_id:
            self.session_manager.revoke_edit_permission(self.receipt_id)
    
    def mark_as_uploader(self):
        """Mark current user as uploader of current receipt"""
        if self.receipt_id:
            self.session_manager.mark_as_uploader(self.receipt_id)
    
    def get_session_context(self):
        """Get session context for service layer compatibility"""
        if not self.receipt_id:
            return {
                'session_key': self.session_id
            }
        return self.session_manager.get_session_context(self.receipt_id)
    
    def with_receipt(self, receipt_id):
        """Create a new UserContext for a different receipt"""
        return UserContext(self.session_manager, receipt_id)