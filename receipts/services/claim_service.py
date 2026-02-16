"""
Service layer for claim operations
Encapsulates all business logic related to claims
"""
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
from fractions import Fraction
from math import gcd
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import transaction

from receipts.models import Claim, LineItem, Receipt
from django.db.models import QuerySet, Sum, F, DecimalField, FloatField, Prefetch, Q, Value
from django.db.models.functions import Coalesce, Cast
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
    @transaction.atomic
    def finalize_claims(self, receipt_id: str, claimer_name: str,
                       claims_data: List[Dict], session_id: str) -> Dict:
        """
        Finalize all claims for a user at once (new total claims protocol)
        Uses atomic transaction with row-level locking to prevent race conditions.

        Args:
            receipt_id: Receipt ID
            claimer_name: Name of the person claiming
            claims_data: List of {"line_item_id": str, "quantity_numerator": int, "quantity_denominator": int}
            session_id: Session ID for ownership verification

        Returns:
            Dict with success status and updated totals

        Raises:
            ValidationError: With detailed availability information on conflicts
        """
        # First, get the receipt to check basic conditions
        try:
            receipt = Receipt.objects.get(id=receipt_id)
        except Receipt.DoesNotExist:
            raise ValueError(f"Receipt {receipt_id} not found")

        if not receipt.is_finalized:
            raise ReceiptNotFinalizedError("Receipt must be finalized before claiming items")

        # Check if user has already finalized
        if Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id,
            is_finalized=True
        ).exists():
            raise ValueError("Claims have already been finalized and cannot be changed")

        # Extract line item IDs we're trying to claim
        line_item_ids = [str(claim_data['line_item_id']) for claim_data in claims_data]

        # CRITICAL: Lock the line items we're trying to claim using select_for_update
        # This prevents other transactions from modifying these items until we're done
        locked_items = LineItem.objects.select_for_update().filter(
            id__in=line_item_ids,
            receipt_id=receipt_id
        ).prefetch_related('claims')

        # Convert to dict for easier lookup
        locked_items_dict = {str(item.id): item for item in locked_items}

        # Now validate with locked rows - no race condition possible!
        validation_errors = []
        availability_info = []

        for claim_data in claims_data:
            line_item_id = str(claim_data['line_item_id'])
            # Shared denominator model: claim numerator is in same units as item numerator
            desired_num = claim_data.get('quantity_numerator', 0)

            # Get the locked line item
            line_item = locked_items_dict.get(line_item_id)
            if not line_item:
                validation_errors.append(f"Item {line_item_id} not found")
                continue

            # Validate quantity is non-negative
            if desired_num < 0:
                validation_errors.append(
                    f"{line_item.name}: Quantity cannot be negative ({desired_num})"
                )
                continue

            # Calculate current availability with locked data (shared denominator)
            claimed_by_others_num = sum(
                claim.quantity_numerator
                for claim in line_item.claims.all()
                if claim.session_id != session_id
            )
            available_num = line_item.quantity_numerator - claimed_by_others_num

            # Track availability for error response
            availability_info.append({
                'item_id': line_item_id,
                'name': line_item.name,
                'requested': desired_num,
                'available': available_num,
            })

            if desired_num > available_num:
                validation_errors.append(
                    f"{line_item.name}: Cannot claim {desired_num}, only {available_num} available"
                )

        # If validation failed, return detailed error with availability info
        if validation_errors:
            error_response = {
                'error': "; ".join(validation_errors),
                'availability': availability_info,
                'preserve_input': True
            }
            # Convert to JSON-serializable format for ValidationError
            import json
            raise ValidationError(json.dumps(error_response))

        # Delete any existing unfinalized claims for this session (within transaction)
        Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id,
            is_finalized=False
        ).delete()

        # Bulk create new finalized claims (shared denominator: only numerator needed)
        claims_to_create = []
        for claim_data in claims_data:
            numerator = claim_data.get('quantity_numerator', 0)
            if numerator > 0:
                claims_to_create.append(Claim(
                    line_item_id=claim_data['line_item_id'],
                    claimer_name=claimer_name,
                    quantity_numerator=numerator,
                    session_id=session_id,
                    is_finalized=True,
                    finalized_at=timezone.now()
                ))

        # Single bulk insert for all claims (within transaction)
        created_claims = Claim.objects.bulk_create(claims_to_create)

        # Invalidate cache since new claims were added
        cache.delete(f"participant_totals:{receipt_id}")
        cache.delete(f"receipt_view:{receipt_id}")

        # Calculate my_total: share = (claim_num / item_num) * total_share
        my_total = Decimal('0')
        for claim in created_claims:
            line_item = locked_items_dict.get(str(claim.line_item_id))
            if line_item and line_item.quantity_numerator > 0:
                share_fraction = Fraction(claim.quantity_numerator, line_item.quantity_numerator)
                total_share = line_item.total_price + line_item.prorated_tax + line_item.prorated_tip
                my_total += Decimal(share_fraction.numerator) / Decimal(share_fraction.denominator) * total_share

        # Get participant totals
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
    
    @transaction.atomic
    def subdivide_item(self, line_item_id: str, target_parts: int) -> Dict:
        """
        Re-split an item on the claim page to `target_parts` total parts.

        target_parts must be a multiple of the irreducible portion count,
        computed as item.quantity_numerator / GCD(item.num, item.den, all claim nums, unclaimed).
        This guarantees all existing claim numerators remain integers.
        """
        if target_parts < 1:
            raise ValueError("target_parts must be >= 1")

        item = LineItem.objects.select_for_update().get(id=line_item_id)
        claims = list(Claim.objects.select_for_update().filter(line_item=item))

        if claims:
            # With existing claims, target must preserve claim integrity
            g, min_parts = self._compute_min_parts(item, claims)

            if target_parts % min_parts != 0:
                raise ValueError(
                    f"Must be a multiple of {min_parts} (try {min_parts}, {min_parts*2}, {min_parts*3})"
                )

            scale_up = target_parts // min_parts

            item.quantity_numerator = target_parts
            item.quantity_denominator = (item.quantity_denominator // g) * scale_up
            item.save(update_fields=['quantity_numerator', 'quantity_denominator'])

            for claim in claims:
                claim.quantity_numerator = (claim.quantity_numerator // g) * scale_up
                claim.save(update_fields=['quantity_numerator'])
        else:
            # No claims — any target is valid, just set directly
            item.quantity_numerator = target_parts
            item.quantity_denominator = target_parts  # N/N = 1 whole item
            item.save(update_fields=['quantity_numerator', 'quantity_denominator'])

        # Invalidate cache
        cache.delete(f"participant_totals:{item.receipt_id}")
        cache.delete(f"receipt_view:{item.receipt_id}")

        return {
            'success': True,
            'quantity_numerator': item.quantity_numerator,
            'quantity_denominator': item.quantity_denominator,
        }

    @staticmethod
    def _compute_min_parts(item, claims):
        """
        Compute the irreducible portion count for an item.

        Returns (g, min_parts) where g is the GCD and min_parts = item.num / g.
        """
        from functools import reduce

        nums = [item.quantity_numerator, item.quantity_denominator]
        claimed_total = 0
        for c in claims:
            nums.append(c.quantity_numerator)
            claimed_total += c.quantity_numerator
        unclaimed = item.quantity_numerator - claimed_total
        if unclaimed > 0:
            nums.append(unclaimed)

        g = reduce(gcd, nums)
        min_parts = item.quantity_numerator // g
        return g, min_parts

    def claim_items(self, receipt_id: str, line_item_id: str,
                   claimer_name: str, quantity: int, session_id: str) -> Claim:
        """
        LEGACY: Process individual incremental claims (deprecated)
        Use finalize_claims() for new total claims protocol
        """
        try:
            receipt = Receipt.objects.select_related().prefetch_related('items').get(id=receipt_id)
        except Receipt.DoesNotExist:
            raise ValueError(f"Receipt {receipt_id} not found")

        if not receipt.is_finalized:
            raise ReceiptNotFinalizedError("Receipt must be finalized before claiming items")

        if self.is_user_finalized(receipt_id, session_id):
            raise ValueError("Claims have already been finalized and cannot be changed")

        try:
            line_item = LineItem.objects.get(id=line_item_id, receipt=receipt)
        except LineItem.DoesNotExist:
            raise ValueError(f"Line item {line_item_id} not found")

        available = self.get_available_quantity(line_item_id)
        if quantity > available:
            raise InsufficientQuantityError(f"Cannot claim {quantity}, only {available} available")

        existing_claim = self._get_existing_claim(line_item_id, session_id)
        if existing_claim:
            return self._update_claim(existing_claim, claimer_name, quantity, 1)
        else:
            return self._create_claim(line_item_id, claimer_name, quantity, 1, session_id)
    
    def undo_claim(self, claim_id: str, session_id: str) -> bool:
        """
        DEPRECATED: Undo logic removed in new protocol.
        Claims are finalized once and cannot be undone.
        """
        claim = self._get_claim_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(f"Claim {claim_id} not found")

        if claim.is_finalized:
            raise ValueError("Finalized claims cannot be undone")

        if claim.session_id != session_id:
            raise PermissionError("Cannot undo another person's claim")

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
        Get the available quantity numerator for a line item (shared denominator).
        """
        try:
            line_item = LineItem.objects.get(id=line_item_id)
            claimed_num = self._count_claimed_numerator(line_item_id)
            return line_item.quantity_numerator - claimed_num
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
        Get all items with availability calculations in single query.
        Shared denominator model: all numerators share the item's denominator.
        """
        items = LineItem.objects.filter(
            receipt_id=receipt_id
        ).annotate(
            total_claimed_num=Coalesce(Sum('claims__quantity_numerator'), Value(0)),
            claimed_by_others_num=Coalesce(
                Sum('claims__quantity_numerator',
                    filter=~Q(claims__session_id=session_id)), Value(0)
            ),
            current_user_claimed_num=Coalesce(
                Sum('claims__quantity_numerator',
                    filter=Q(claims__session_id=session_id)), Value(0)
            ),
        ).select_related('receipt')

        for item in items:
            item.available_for_session = item.quantity_numerator - item.claimed_by_others_num

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
        """Calculate totals per participant. share = claim_num / item_num * total_share"""
        if not Receipt.objects.filter(id=receipt_id).exists():
            return {}

        # Cast to FloatField to force float division in SQLite (avoids integer truncation)
        results = Claim.objects.filter(
            line_item__receipt_id=receipt_id
        ).values('claimer_name').annotate(
            total=Sum(
                (Cast(F('quantity_numerator'), FloatField())
                 / Cast(F('line_item__quantity_numerator'), FloatField()))
                * (F('line_item__total_price') + F('line_item__prorated_tax') + F('line_item__prorated_tip')),
                output_field=DecimalField(max_digits=12, decimal_places=6)
            )
        ).order_by('claimer_name')

        return {
            result['claimer_name']: result['total'] or Decimal('0')
            for result in results
        }
    
    def _count_claimed_numerator(self, line_item_id: str) -> int:
        """Get total claimed numerator for a line item (shared denominator)."""
        result = Claim.objects.filter(line_item_id=line_item_id).aggregate(
            total=Sum('quantity_numerator')
        )['total'] or 0
        return result
    
    def _get_available_quantity_excluding_session(self, line_item_id: str, session_id: str) -> int:
        """Get available numerator quantity excluding current session's claims"""
        try:
            line_item = LineItem.objects.get(id=line_item_id)
            claimed_by_others = Claim.objects.filter(
                line_item_id=line_item_id
            ).exclude(session_id=session_id).aggregate(
                total=Sum('quantity_numerator')
            )['total'] or 0
            return line_item.quantity_numerator - claimed_by_others
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
                     quantity_numerator: int, quantity_denominator: int, session_id: str) -> Claim:
        """Create a new claim (legacy method)"""
        return Claim.objects.create(
            line_item_id=line_item_id,
            claimer_name=claimer_name,
            quantity_numerator=quantity_numerator,
            session_id=session_id,
        )

    def _create_finalized_claim(self, line_item_id: str, claimer_name: str,
                               quantity_numerator: int, quantity_denominator: int, session_id: str) -> Claim:
        """Create a new finalized claim"""
        return Claim.objects.create(
            line_item_id=line_item_id,
            claimer_name=claimer_name,
            quantity_numerator=quantity_numerator,
            session_id=session_id,
            is_finalized=True,
            finalized_at=timezone.now()
        )

    def _update_claim(self, claim: Claim, claimer_name: str,
                     quantity_numerator: int, quantity_denominator: int) -> Claim:
        """Update an existing claim"""
        claim.claimer_name = claimer_name
        claim.quantity_numerator = quantity_numerator
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