"""
Service layer for receipt operations
Encapsulates all business logic related to receipts
"""
from typing import Dict, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.signing import Signer, BadSignature

from receipts.models import Receipt, LineItem, ActiveViewer
from receipts.repositories import ReceiptRepository, ClaimRepository
from receipts.services.validation_pipeline import ValidationPipeline
from receipts.async_processor import process_receipt_async, create_placeholder_receipt
from receipts.image_storage import store_receipt_image_in_memory


class ReceiptNotFoundError(Exception):
    pass


class ReceiptAlreadyFinalizedError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


class ReceiptService:
    """Handles all business logic for receipts"""
    
    def __init__(self):
        self.repository = ReceiptRepository()
        self.claim_repository = ClaimRepository()
        self.validator = ValidationPipeline()
        self.signer = Signer()
    
    def create_receipt(self, uploader_name: str, image_file) -> Receipt:
        """
        Create a new receipt with async OCR processing
        """
        # Validate inputs
        validated_name = self.validator.validate_name(uploader_name, "Your name")
        validated_image = self.validator.validate_image_file(image_file)
        
        # Create placeholder receipt
        receipt = create_placeholder_receipt(validated_name, validated_image)
        
        # Start async OCR processing
        process_receipt_async(receipt.id, validated_image)
        
        return receipt
    
    def get_receipt_by_id(self, receipt_id: str) -> Optional[Receipt]:
        """Get receipt by ID"""
        return self.repository.get_by_id(receipt_id)
    
    def get_receipt_by_slug(self, slug: str) -> Optional[Receipt]:
        """Get receipt by slug"""
        return self.repository.get_by_slug(slug)
    
    def update_receipt(self, receipt_id: str, data: Dict, 
                      session_context: Dict) -> Dict:
        """
        Update receipt with validation
        Allows saving even if data doesn't balance (business requirement)
        """
        # Get receipt
        receipt = self.repository.get_by_id(receipt_id)
        if not receipt:
            raise ReceiptNotFoundError(f"Receipt {receipt_id} not found")
        
        # Check permissions
        if receipt.is_finalized:
            raise ReceiptAlreadyFinalizedError("Receipt is already finalized")
        
        if not self._verify_edit_permission(receipt, session_context):
            raise PermissionDeniedError("You don't have permission to edit this receipt")
        
        # Validate data (but allow saving even if invalid)
        validated_data, validation_errors = self.validator.validate_receipt_data(data)
        
        # Update receipt
        update_data = {
            'restaurant_name': validated_data.get('restaurant_name', receipt.restaurant_name),
            'subtotal': Decimal(str(validated_data.get('subtotal', receipt.subtotal))),
            'tax': Decimal(str(validated_data.get('tax', receipt.tax))),
            'tip': Decimal(str(validated_data.get('tip', receipt.tip))),
            'total': Decimal(str(validated_data.get('total', receipt.total))),
        }
        
        # Add items if provided
        if 'items' in validated_data:
            update_data['items'] = [
                {
                    'name': item['name'],
                    'quantity': item['quantity'],
                    'unit_price': Decimal(str(item['unit_price'])),
                    'total_price': Decimal(str(item['total_price']))
                }
                for item in validated_data['items']
            ]
        
        # Update through repository
        updated_receipt = self.repository.update_receipt_with_items(receipt, update_data)
        
        # Prepare response
        response = {
            'success': True,
            'is_balanced': not bool(validation_errors and 
                                   any(key not in ['warnings'] for key in validation_errors.keys()))
        }
        
        if validation_errors:
            response['validation_errors'] = validation_errors
        
        return response
    
    def finalize_receipt(self, receipt_id: str, session_context: Dict) -> Dict:
        """
        Finalize receipt with strict validation
        """
        # Get receipt
        receipt = self.repository.get_by_id(receipt_id)
        if not receipt:
            raise ReceiptNotFoundError(f"Receipt {receipt_id} not found")
        
        # Check if already finalized
        if receipt.is_finalized:
            raise ReceiptAlreadyFinalizedError("Receipt is already finalized")
        
        # Check permission (only uploader can finalize)
        if session_context.get('receipt_id') != str(receipt_id):
            raise PermissionDeniedError("Only the uploader can finalize the receipt")
        
        # Get receipt data for validation
        receipt_data = self.repository.get_receipt_data_for_validation(receipt)
        
        # Strict validation for finalization
        is_valid, validation_errors = self.validator.validate_for_finalization(receipt_data)
        
        if not is_valid:
            error_message = "Receipt doesn't balance. Please fix the following issues:\n"
            error_message += self.validator.format_validation_errors(validation_errors)
            
            raise ValidationError(error_message, params={
                'validation_errors': validation_errors
            })
        
        # Finalize the receipt
        self.repository.finalize_receipt(receipt_id)
        
        return {
            'success': True,
            'share_url': receipt.get_absolute_url()
        }
    
    def get_receipt_for_viewing(self, receipt_id: str) -> Dict:
        """
        Get receipt with all claims and calculations for viewing
        """
        # Get receipt with all related data
        receipt = self.repository.get_with_claims_and_viewers(receipt_id)
        if not receipt:
            raise ReceiptNotFoundError(f"Receipt {receipt_id} not found")
        
        # Prepare items with claims data
        items_with_claims = []
        for item in receipt.items.all():
            claims = item.claims.all()
            items_with_claims.append({
                'item': item,
                'claims': claims,
                'available_quantity': item.get_available_quantity()
            })
        
        # Calculate participant totals
        participant_totals = self.claim_repository.get_participant_totals(receipt_id)
        
        # Calculate summary
        total_claimed = sum(participant_totals.values())
        total_unclaimed = receipt.total - total_claimed
        
        # Sort participants by name
        participant_list = sorted([
            {'name': name, 'amount': amount}
            for name, amount in participant_totals.items()
        ], key=lambda x: x['name'])
        
        return {
            'receipt': receipt,
            'items_with_claims': items_with_claims,
            'participant_totals': participant_list,
            'total_claimed': total_claimed,
            'total_unclaimed': total_unclaimed
        }
    
    def register_viewer(self, receipt_id: str, viewer_name: str, session_id: str) -> ActiveViewer:
        """Register a viewer for the receipt"""
        receipt = self.repository.get_by_id(receipt_id)
        if not receipt:
            raise ReceiptNotFoundError(f"Receipt {receipt_id} not found")
        
        viewer, created = ActiveViewer.objects.update_or_create(
            receipt=receipt,
            session_id=session_id,
            defaults={'viewer_name': viewer_name}
        )
        
        return viewer
    
    def get_existing_names(self, receipt_id: str) -> list:
        """Get all existing viewer and claimer names for a receipt"""
        receipt = self.repository.get_with_claims_and_viewers(receipt_id)
        if not receipt:
            return []
        
        names = list(receipt.viewers.values_list('viewer_name', flat=True))
        names.extend(self.claim_repository.get_all_claimer_names(receipt_id))
        
        return list(set(names))  # Remove duplicates
    
    def create_edit_token(self, receipt_id: str, session_key: str) -> str:
        """Create a secure edit token for a receipt"""
        data = f"{receipt_id}:{session_key}"
        return self.signer.sign(data)
    
    def _verify_edit_permission(self, receipt: Receipt, session_context: Dict) -> bool:
        """Verify if user has permission to edit receipt"""
        if receipt.is_finalized:
            return False
        
        # Check if user uploaded this receipt
        if session_context.get('receipt_id') == str(receipt.id):
            return True
        
        # Check for edit token
        stored_token = session_context.get(f'edit_token_{receipt.id}')
        if not stored_token:
            return False
        
        try:
            unsigned = self.signer.unsign(stored_token)
            receipt_id, session_key = unsigned.split(':')
            return (str(receipt.id) == receipt_id and 
                   session_context.get('session_key') == session_key)
        except (BadSignature, ValueError):
            return False