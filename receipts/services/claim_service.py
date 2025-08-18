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
    
    def finalize_claims(self, receipt_id: str, claimer_name: str, 
                       claims_data: List[Dict], session_id: str) -> Dict:
        """
        Finalize all claims for a user at once (new total claims protocol)
        
        Args:
            receipt_id: Receipt ID
            claimer_name: Name of the person claiming
            claims_data: List of {"line_item_id": str, "quantity": int} (total desired quantities)
            session_id: Session ID for ownership verification
            
        Returns:
            Dict with success status and updated totals
        """
        # Verify receipt exists and is finalized
        receipt = self.receipt_repository.get_by_id(receipt_id)
        if not receipt:
            raise ValueError(f"Receipt {receipt_id} not found")
        
        if not receipt.is_finalized:
            raise ReceiptNotFinalizedError("Receipt must be finalized before claiming items")
        
        # Check if user has already finalized their claims
        existing_finalized_claims = Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id,
            is_finalized=True
        )
        
        if existing_finalized_claims.exists():
            raise ValueError("Claims have already been finalized and cannot be changed")
        
        # Validate all claims first (fail fast)
        validation_errors = []
        for claim_data in claims_data:
            line_item_id = claim_data['line_item_id']
            desired_quantity = claim_data['quantity']
            
            # Get line item
            try:
                line_item = LineItem.objects.get(id=line_item_id, receipt=receipt)
            except LineItem.DoesNotExist:
                validation_errors.append(f"Item {line_item_id} not found")
                continue
            
            # Validate quantity is non-negative
            if desired_quantity < 0:
                validation_errors.append(
                    f"{line_item.name}: Quantity cannot be negative ({desired_quantity})"
                )
                continue
            
            # Check availability (excluding this user's current claims)
            available_for_others = self.repository.get_available_quantity_excluding_session(
                line_item_id, session_id
            )
            
            if desired_quantity > available_for_others:
                validation_errors.append(
                    f"{line_item.name}: Cannot claim {desired_quantity}, only {available_for_others} available"
                )
        
        if validation_errors:
            raise ValidationError("; ".join(validation_errors))
        
        # Delete any existing unfinalied claims for this session
        Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id,
            is_finalized=False
        ).delete()
        
        # Create new finalized claims
        created_claims = []
        for claim_data in claims_data:
            if claim_data['quantity'] > 0:  # Only create claims for positive quantities
                claim = self.repository.create_finalized_claim(
                    line_item_id=claim_data['line_item_id'],
                    claimer_name=claimer_name,
                    quantity_claimed=claim_data['quantity'],
                    session_id=session_id
                )
                created_claims.append(claim)
        
        # Calculate new totals
        my_total = self.calculate_name_total(receipt_id, claimer_name)
        participant_totals = self.get_participant_totals(receipt_id)
        
        return {
            'success': True,
            'finalized': True,
            'claims_count': len(created_claims),
            'my_total': float(my_total),
            'participant_totals': {
                name: float(amount) 
                for name, amount in participant_totals.items()
            }
        }
    
    def claim_items(self, receipt_id: str, line_item_id: str, 
                   claimer_name: str, quantity: int, session_id: str) -> Claim:
        """
        LEGACY: Process individual incremental claims (deprecated)
        Use finalize_claims() for new total claims protocol
        """
        # Verify receipt exists and is finalized
        receipt = self.receipt_repository.get_by_id(receipt_id)
        if not receipt:
            raise ValueError(f"Receipt {receipt_id} not found")
        
        if not receipt.is_finalized:
            raise ReceiptNotFinalizedError("Receipt must be finalized before claiming items")
        
        # Check if user has already finalized their claims
        if self.is_user_finalized(receipt_id, session_id):
            raise ValueError("Claims have already been finalized and cannot be changed")
        
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
        DEPRECATED: Undo logic removed in new protocol
        Claims are finalized once and cannot be undone
        """
        # Check if claim is finalized
        claim = self.repository.get_claim_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(f"Claim {claim_id} not found")
        
        if claim.is_finalized:
            raise ValueError("Finalized claims cannot be undone")
        
        # For legacy unfinalied claims, allow undo if within grace period
        if claim.session_id != session_id:
            raise PermissionError("Cannot undo another person's claim")
        
        if not claim.is_within_grace_period():
            raise GracePeriodExpiredError("Grace period for undoing this claim has expired")
        
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
    
    def is_user_finalized(self, receipt_id: str, session_id: str) -> bool:
        """
        Check if a user has finalized their claims
        """
        return Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id,
            is_finalized=True
        ).exists()
    
    def get_user_pending_claims(self, receipt_id: str, session_id: str) -> List[Claim]:
        """
        Get user's pending (unfinalized) claims
        """
        return list(Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id,
            is_finalized=False
        ).select_related('line_item'))
    
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