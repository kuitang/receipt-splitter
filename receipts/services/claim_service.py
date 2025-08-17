"""
Service layer for claim operations
Encapsulates all business logic related to claims
"""
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta

from receipts.models import Claim, LineItem, Receipt
from receipts.repositories import ClaimRepository, ReceiptRepository
from receipts.services.validation_pipeline import ValidationPipeline


class ClaimNotFoundError(Exception):
    pass


class InsufficientQuantityError(Exception):
    pass


class ReceiptNotFinalizedError(Exception):
    pass


class GracePeriodExpiredError(Exception):
    pass


class ClaimService:
    """Handles all business logic for claims"""
    
    def __init__(self):
        self.repository = ClaimRepository()
        self.receipt_repository = ReceiptRepository()
        self.validator = ValidationPipeline()
    
    def claim_items(self, receipt_id: str, line_item_id: str, 
                   claimer_name: str, quantity: int, session_id: str) -> Claim:
        """
        Process a claim for line items
        """
        # Verify receipt exists and is finalized
        receipt = self.receipt_repository.get_by_id(receipt_id)
        if not receipt:
            raise ValueError(f"Receipt {receipt_id} not found")
        
        if not receipt.is_finalized:
            raise ReceiptNotFinalizedError("Receipt must be finalized before claiming items")
        
        # Get line item
        try:
            line_item = LineItem.objects.get(id=line_item_id, receipt=receipt)
        except LineItem.DoesNotExist:
            raise ValueError(f"Line item {line_item_id} not found")
        
        # Check availability
        available_quantity = self.repository.get_available_quantity(line_item_id)
        is_valid, error_msg = self.validator.validate_claim_request(
            line_item_id, quantity, available_quantity
        )
        
        if not is_valid:
            raise InsufficientQuantityError(error_msg)
        
        # Check for existing claim
        existing_claim = self.repository.get_existing_claim(line_item_id, session_id)
        
        if existing_claim:
            # Update existing claim
            return self.repository.update_claim(existing_claim, claimer_name, quantity)
        else:
            # Create new claim
            return self.repository.create_claim(
                line_item_id, claimer_name, quantity, session_id
            )
    
    def undo_claim(self, claim_id: str, session_id: str) -> bool:
        """
        Undo a claim within the grace period
        """
        # Get the claim
        claim = self.repository.get_claim_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(f"Claim {claim_id} not found")
        
        # Verify ownership
        if claim.session_id != session_id:
            raise PermissionError("Cannot undo another person's claim")
        
        # Check grace period
        if not claim.is_within_grace_period():
            raise GracePeriodExpiredError("Grace period for undoing this claim has expired")
        
        # Delete the claim
        return self.repository.delete_claim(claim_id)
    
    def get_claims_for_session(self, receipt_id: str, session_id: str) -> List[Claim]:
        """
        Get all claims for a specific session on a receipt
        """
        return list(self.repository.get_claims_by_session(receipt_id, session_id))
    
    def get_claims_for_name(self, receipt_id: str, claimer_name: str) -> List[Claim]:
        """
        Get all claims for a specific claimer name on a receipt
        """
        return list(self.repository.get_claims_by_name(receipt_id, claimer_name))
    
    def get_participant_totals(self, receipt_id: str) -> Dict[str, Decimal]:
        """
        Calculate total amounts claimed by each participant
        """
        return self.repository.get_participant_totals(receipt_id)
    
    def calculate_session_total(self, receipt_id: str, session_id: str) -> Decimal:
        """
        Calculate total amount for a specific session
        """
        claims = self.repository.get_claims_by_session(receipt_id, session_id)
        total = Decimal('0')
        
        for claim in claims:
            total += claim.get_share_amount()
        
        return total
    
    def calculate_name_total(self, receipt_id: str, claimer_name: str) -> Decimal:
        """
        Calculate total amount for a specific claimer name
        """
        claims = self.repository.get_claims_by_name(receipt_id, claimer_name)
        total = Decimal('0')
        
        for claim in claims:
            total += claim.get_share_amount()
        
        return total
    
    def get_available_quantity(self, line_item_id: str) -> int:
        """
        Get the available quantity for a line item
        """
        return self.repository.get_available_quantity(line_item_id)
    
    def validate_claimer_name(self, receipt_id: str, name: str, 
                             existing_names: Optional[List[str]] = None) -> Tuple[bool, Optional[List[str]]]:
        """
        Validate a claimer name and return suggestions if there's a collision
        """
        # Validate the name format
        try:
            validated_name = self.validator.validate_name(name, "Your name")
        except ValidationError:
            return False, None
        
        # Check for name collision
        if existing_names is None:
            existing_names = self.repository.get_all_claimer_names(receipt_id)
        
        if validated_name in existing_names:
            # Generate suggestions
            suggestions = [
                f"{validated_name} 2",
                f"{validated_name}_guest",
                f"{validated_name} (Guest)"
            ]
            return False, suggestions
        
        return True, None