"""
Service layer for claim operations
Encapsulates all business logic related to claims
"""
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.cache import cache
from datetime import timedelta

from receipts.models import Claim, LineItem, Receipt
from django.db.models import QuerySet, Sum, F, DecimalField, Prefetch, Q, Value
from django.db.models.functions import Coalesce
from receipts.services.validation_pipeline import ValidationPipeline
from receipts.middleware.query_monitor import log_query_performance


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
        self.validator = ValidationPipeline()
    
    @log_query_performance
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
        # Verify receipt exists and is finalized (with prefetch for efficiency)
        try:
            receipt = Receipt.objects.prefetch_related(
                'items',
                'items__claims'
            ).get(id=receipt_id)
        except Receipt.DoesNotExist:
            raise ValueError(f"Receipt {receipt_id} not found")
        
        if not receipt.is_finalized:
            raise ReceiptNotFinalizedError("Receipt must be finalized before claiming items")
        
        # Check if user has already finalized their claims (single exists check)
        if Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id,
            is_finalized=True
        ).exists():
            raise ValueError("Claims have already been finalized and cannot be changed")
        
        # Build lookup dictionaries from prefetched data (no additional queries!)
        line_items_dict = {str(item.id): item for item in receipt.items.all()}
        
        # Get all availability data in a SINGLE query
        # Ensure item_ids are strings for consistency
        item_ids = [str(claim_data['line_item_id']) for claim_data in claims_data]
        availability_data = {}
        if item_ids:
            # Single aggregated query for all items' availability
            availability_results = Claim.objects.filter(
                line_item_id__in=item_ids
            ).exclude(
                session_id=session_id
            ).values('line_item_id').annotate(
                claimed_by_others=Sum('quantity_claimed')
            )
            
            # Convert to dict for O(1) lookups
            for result in availability_results:
                availability_data[str(result['line_item_id'])] = result['claimed_by_others'] or 0
        
        # Validate all claims using cached data (no queries in this loop!)
        validation_errors = []
        for claim_data in claims_data:
            line_item_id = str(claim_data['line_item_id'])  # Ensure string for dict lookup
            desired_quantity = claim_data['quantity']
            
            # Get line item from prefetched dict
            line_item = line_items_dict.get(line_item_id)
            if not line_item:
                validation_errors.append(f"Item {line_item_id} not found")
                continue
            
            # Validate quantity is non-negative
            if desired_quantity < 0:
                validation_errors.append(
                    f"{line_item.name}: Quantity cannot be negative ({desired_quantity})"
                )
                continue
            
            # Check availability using pre-calculated data
            claimed_by_others = availability_data.get(line_item_id, 0)
            available = line_item.quantity - claimed_by_others
            
            if desired_quantity > available:
                validation_errors.append(
                    f"{line_item.name}: Cannot claim {desired_quantity}, only {available} available"
                )
        
        if validation_errors:
            raise ValidationError("; ".join(validation_errors))
        
        # Delete any existing unfinalied claims for this session
        Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id,
            is_finalized=False
        ).delete()
        
        # Bulk create new finalized claims
        claims_to_create = []
        for claim_data in claims_data:
            if claim_data['quantity'] > 0:  # Only create claims for positive quantities
                claims_to_create.append(Claim(
                    line_item_id=claim_data['line_item_id'],  # Use original format
                    claimer_name=claimer_name,
                    quantity_claimed=claim_data['quantity'],
                    session_id=session_id,
                    is_finalized=True,
                    finalized_at=timezone.now()
                ))
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[finalize_claims] Creating {len(claims_to_create)} claims for claimer_name='{claimer_name}', session_id={session_id}")
        
        # Single bulk insert for all claims
        created_claims = Claim.objects.bulk_create(claims_to_create)
        
        # Invalidate cache since new claims were added
        cache.delete(f"participant_totals:{receipt_id}")
        cache.delete(f"receipt_view:{receipt_id}")
        
        # Calculate my_total directly from created claims (no additional query!)
        my_total = Decimal('0')
        for claim in created_claims:
            # Get the line item from our prefetched dict
            line_item = line_items_dict.get(str(claim.line_item_id))
            if line_item:
                # Calculate share amount without fetching from DB
                unit_price = line_item.total_price / line_item.quantity if line_item.quantity else Decimal('0')
                prorated_tax = line_item.prorated_tax / line_item.quantity if line_item.quantity else Decimal('0')
                prorated_tip = line_item.prorated_tip / line_item.quantity if line_item.quantity else Decimal('0')
                my_total += claim.quantity_claimed * (unit_price + prorated_tax + prorated_tip)
        
        # Get participant totals (this is already optimized with single query)
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
        try:
            receipt = Receipt.objects.select_related().prefetch_related('items').get(id=receipt_id)
        except Receipt.DoesNotExist:
            receipt = None
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
        available_quantity = self.get_available_quantity(line_item_id)
        is_valid, error_msg = self.validator.validate_claim_request(
            line_item_id, quantity, available_quantity
        )
        
        if not is_valid:
            raise InsufficientQuantityError(error_msg)
        
        # Check for existing claim
        existing_claim = self._get_existing_claim(line_item_id, session_id)
        
        if existing_claim:
            # Update existing claim
            return self._update_claim(existing_claim, claimer_name, quantity)
        else:
            # Create new claim
            return self._create_claim(
                line_item_id, claimer_name, quantity, session_id
            )
    
    def undo_claim(self, claim_id: str, session_id: str) -> bool:
        """
        DEPRECATED: Undo logic removed in new protocol
        Claims are finalized once and cannot be undone
        """
        # Check if claim is finalized
        claim = self._get_claim_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(f"Claim {claim_id} not found")
        
        if claim.is_finalized:
            raise ValueError("Finalized claims cannot be undone")
        
        # For legacy unfinalied claims, allow undo if within grace period
        if claim.session_id != session_id:
            raise PermissionError("Cannot undo another person's claim")
        
        if not claim.is_within_grace_period():
            raise GracePeriodExpiredError("Grace period for undoing this claim has expired")
        
        return self._delete_claim(claim_id)
    
    def get_claims_for_session(self, receipt_id: str, session_id: str) -> List[Claim]:
        """
        Get all claims for a specific session on a receipt
        """
        return list(self._get_claims_by_session(receipt_id, session_id))
    
    def get_claims_for_name(self, receipt_id: str, claimer_name: str) -> List[Claim]:
        """
        Get all claims for a specific claimer name on a receipt
        """
        return list(self._get_claims_by_name(receipt_id, claimer_name))
    
    @log_query_performance
    def get_participant_totals(self, receipt_id: str) -> Dict[str, Decimal]:
        """
        Calculate total amounts claimed by each participant
        Uses cache for finalized receipts
        """
        # Check if receipt is finalized
        cache_key = f"participant_totals:{receipt_id}"
        
        # Try to get from cache if receipt is finalized
        try:
            receipt = Receipt.objects.only('is_finalized').get(id=receipt_id)
            if receipt.is_finalized:
                cached = cache.get(cache_key)
                if cached is not None:
                    return cached
        except Receipt.DoesNotExist:
            return {}
        
        # Calculate totals
        totals = self._get_participant_totals(receipt_id)
        
        # Cache if finalized (1 hour)
        if receipt.is_finalized:
            cache.set(cache_key, totals, 3600)
        
        return totals
    
    def calculate_session_total(self, receipt_id: str, session_id: str) -> Decimal:
        """
        Calculate total amount for a specific session
        """
        claims = self._get_claims_by_session(receipt_id, session_id)
        total = Decimal('0')
        
        for claim in claims:
            total += claim.get_share_amount()
        
        return total
    
    def calculate_name_total(self, receipt_id: str, claimer_name: str) -> Decimal:
        """
        Calculate total amount for a specific claimer name
        """
        claims = self._get_claims_by_name(receipt_id, claimer_name)
        total = Decimal('0')
        
        for claim in claims:
            total += claim.get_share_amount()
        
        return total
    
    def get_available_quantity(self, line_item_id: str) -> int:
        """
        Get the available quantity for a line item
        """
        try:
            line_item = LineItem.objects.get(id=line_item_id)
            claimed = self._count_claimed_quantity(line_item_id)
            return line_item.quantity - claimed
        except LineItem.DoesNotExist:
            return 0
    
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
            existing_names = self._get_all_claimer_names(receipt_id)
        
        if validated_name in existing_names:
            # Generate suggestions
            suggestions = [
                f"{validated_name} 2",
                f"{validated_name}_guest",
                f"{validated_name} (Guest)"
            ]
            return False, suggestions
        
        return True, None
    
    def get_items_with_availability(self, receipt_id: str, session_id: str) -> List[Dict]:
        """
        Get all items with availability calculations in single query
        Optimized to avoid N+1 queries when checking claim availability
        """
        # Single query with all availability calculations
        items = LineItem.objects.filter(
            receipt_id=receipt_id
        ).annotate(
            total_claimed=Coalesce(Sum('claims__quantity_claimed'), Value(0)),
            claimed_by_others=Coalesce(
                Sum('claims__quantity_claimed', 
                    filter=~Q(claims__session_id=session_id)), Value(0)
            ),
            available_for_session=F('quantity') - F('claimed_by_others'),
            current_user_claimed=Coalesce(
                Sum('claims__quantity_claimed',
                    filter=Q(claims__session_id=session_id)), Value(0)
            )
        ).select_related('receipt')
        
        return list(items)
    
    # Private methods (formerly in ClaimRepository)
    
    def _get_claims_by_session(self, receipt_id: str, session_id: str) -> QuerySet:
        """Get claims for a specific session"""
        return Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id
        ).select_related('line_item')
    
    def _get_claims_by_name(self, receipt_id: str, claimer_name: str) -> QuerySet:
        """Get claims for a specific claimer name"""
        return Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            claimer_name=claimer_name
        ).select_related('line_item')
    
    def _get_claim_by_id(self, claim_id: str) -> Optional[Claim]:
        """Get a single claim by ID"""
        try:
            return Claim.objects.select_related('line_item').get(id=claim_id)
        except Claim.DoesNotExist:
            return None
    
    def _get_participant_totals(self, receipt_id: str) -> Dict[str, Decimal]:
        """Calculate totals per participant efficiently using single database query"""
        # Verify receipt exists
        if not Receipt.objects.filter(id=receipt_id).exists():
            return {}
        
        # Single aggregation query to calculate all participant totals
        # This replaces the N+1 query pattern where get_share_amount() was called for each claim
        results = Claim.objects.filter(
            line_item__receipt_id=receipt_id
        ).values('claimer_name').annotate(
            total=Sum(
                F('quantity_claimed') * (
                    F('line_item__total_price') / F('line_item__quantity') +
                    F('line_item__prorated_tax') / F('line_item__quantity') +
                    F('line_item__prorated_tip') / F('line_item__quantity')
                ),
                output_field=DecimalField(max_digits=12, decimal_places=6)
            )
        ).order_by('claimer_name')
        
        # Convert to dictionary
        participant_totals = {
            result['claimer_name']: result['total'] or Decimal('0')
            for result in results
        }
        
        return participant_totals
    
    def _count_claimed_quantity(self, line_item_id: str) -> int:
        """Get total claimed quantity for a line item"""
        result = Claim.objects.filter(
            line_item_id=line_item_id
        ).aggregate(total=Sum('quantity_claimed'))
        
        return result['total'] or 0
    
    def _get_available_quantity_excluding_session(self, line_item_id: str, session_id: str) -> int:
        """Get available quantity excluding current session's claims"""
        try:
            line_item = LineItem.objects.get(id=line_item_id)
            
            # Count claims from other sessions only
            claimed_by_others = Claim.objects.filter(
                line_item_id=line_item_id
            ).exclude(session_id=session_id).aggregate(
                total=Sum('quantity_claimed')
            )['total'] or 0
            
            return line_item.quantity - claimed_by_others
        except LineItem.DoesNotExist:
            return 0
    
    def _get_existing_claim(self, line_item_id: str, session_id: str) -> Optional[Claim]:
        """Get existing claim for a line item and session"""
        try:
            return Claim.objects.get(
                line_item_id=line_item_id,
                session_id=session_id
            )
        except Claim.DoesNotExist:
            return None
    
    def _create_claim(self, line_item_id: str, claimer_name: str, 
                     quantity_claimed: int, session_id: str) -> Claim:
        """Create a new claim (legacy method)"""
        grace_period_ends = timezone.now() + timedelta(seconds=30)
        
        return Claim.objects.create(
            line_item_id=line_item_id,
            claimer_name=claimer_name,
            quantity_claimed=quantity_claimed,
            session_id=session_id,
            grace_period_ends=grace_period_ends
        )
    
    def _create_finalized_claim(self, line_item_id: str, claimer_name: str, 
                               quantity_claimed: int, session_id: str) -> Claim:
        """Create a new finalized claim (new total claims protocol)"""
        return Claim.objects.create(
            line_item_id=line_item_id,
            claimer_name=claimer_name,
            quantity_claimed=quantity_claimed,
            session_id=session_id,
            is_finalized=True,
            finalized_at=timezone.now()
        )
    
    def _update_claim(self, claim: Claim, claimer_name: str, 
                     quantity_claimed: int) -> Claim:
        """Update an existing claim"""
        claim.claimer_name = claimer_name
        claim.quantity_claimed = quantity_claimed
        claim.grace_period_ends = timezone.now() + timedelta(seconds=30)
        claim.save()
        return claim
    
    def _delete_claim(self, claim_id: str) -> bool:
        """Delete a claim and return success status"""
        deleted_count, _ = Claim.objects.filter(id=claim_id).delete()
        return deleted_count > 0
    
    def _get_all_claimer_names(self, receipt_id: str) -> List[str]:
        """Get all unique claimer names for a receipt"""
        names = Claim.objects.filter(
            line_item__receipt_id=receipt_id
        ).values_list('claimer_name', flat=True).distinct()
        
        return list(names)