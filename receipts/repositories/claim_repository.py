"""
Repository for Claim data access
Encapsulates all database queries related to claims
"""
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import timedelta
from django.db.models import QuerySet, Sum, F, DecimalField
from django.db import models
from django.utils import timezone

from receipts.models import Claim, LineItem


class ClaimRepository:
    """Handles all data access for claims"""
    
    def get_claims_for_receipt(self, receipt_id: str) -> QuerySet:
        """Get all claims for a receipt with optimized query"""
        return Claim.objects.filter(
            line_item__receipt_id=receipt_id
        ).select_related('line_item').order_by('claimed_at')
    
    def get_claims_by_session(self, receipt_id: str, session_id: str) -> QuerySet:
        """Get claims for a specific session"""
        return Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            session_id=session_id
        ).select_related('line_item')
    
    def get_claims_by_name(self, receipt_id: str, claimer_name: str) -> QuerySet:
        """Get claims for a specific claimer name"""
        return Claim.objects.filter(
            line_item__receipt_id=receipt_id,
            claimer_name=claimer_name
        ).select_related('line_item')
    
    def get_claim_by_id(self, claim_id: str) -> Optional[Claim]:
        """Get a single claim by ID"""
        try:
            return Claim.objects.select_related('line_item').get(id=claim_id)
        except Claim.DoesNotExist:
            return None
    
    def get_participant_totals(self, receipt_id: str) -> Dict[str, Decimal]:
        """Calculate totals per participant efficiently"""
        from receipts.models import Receipt
        
        # Get the receipt for calculations
        try:
            receipt = Receipt.objects.get(id=receipt_id)
        except Receipt.DoesNotExist:
            return {}
        
        # Get all claims with their line items
        claims = Claim.objects.filter(
            line_item__receipt_id=receipt_id
        ).select_related('line_item')
        
        # Calculate totals manually to match existing logic
        participant_totals = {}
        for claim in claims:
            if claim.claimer_name not in participant_totals:
                participant_totals[claim.claimer_name] = Decimal('0')
            participant_totals[claim.claimer_name] += claim.get_share_amount()
        
        return participant_totals
    
    def count_claimed_quantity(self, line_item_id: str) -> int:
        """Get total claimed quantity for a line item"""
        result = Claim.objects.filter(
            line_item_id=line_item_id
        ).aggregate(total=Sum('quantity_claimed'))
        
        return result['total'] or 0
    
    def get_available_quantity(self, line_item_id: str) -> int:
        """Get available quantity for a line item"""
        try:
            line_item = LineItem.objects.get(id=line_item_id)
            claimed = self.count_claimed_quantity(line_item_id)
            return line_item.quantity - claimed
        except LineItem.DoesNotExist:
            return 0
    
    def get_available_quantity_excluding_session(self, line_item_id: str, session_id: str) -> int:
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
    
    def get_existing_claim(self, line_item_id: str, session_id: str) -> Optional[Claim]:
        """Get existing claim for a line item and session"""
        try:
            return Claim.objects.get(
                line_item_id=line_item_id,
                session_id=session_id
            )
        except Claim.DoesNotExist:
            return None
    
    def create_claim(self, line_item_id: str, claimer_name: str, 
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
    
    def create_finalized_claim(self, line_item_id: str, claimer_name: str, 
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
    
    def update_claim(self, claim: Claim, claimer_name: str, 
                    quantity_claimed: int) -> Claim:
        """Update an existing claim"""
        claim.claimer_name = claimer_name
        claim.quantity_claimed = quantity_claimed
        claim.grace_period_ends = timezone.now() + timedelta(seconds=30)
        claim.save()
        return claim
    
    def create_or_update_claim(self, line_item_id: str, session_id: str,
                              claimer_name: str, quantity: int) -> Claim:
        """Create or update claim atomically"""
        claim, created = Claim.objects.update_or_create(
            line_item_id=line_item_id,
            session_id=session_id,
            defaults={
                'claimer_name': claimer_name,
                'quantity_claimed': quantity,
                'grace_period_ends': timezone.now() + timedelta(seconds=30)
            }
        )
        return claim
    
    def delete_claim(self, claim_id: str) -> bool:
        """Delete a claim and return success status"""
        deleted_count, _ = Claim.objects.filter(id=claim_id).delete()
        return deleted_count > 0
    
    def delete_claim_if_within_grace_period(self, claim_id: str, session_id: str) -> bool:
        """Delete claim only if within grace period and belongs to session"""
        deleted_count, _ = Claim.objects.filter(
            id=claim_id,
            session_id=session_id,
            grace_period_ends__gt=timezone.now()
        ).delete()
        return deleted_count > 0
    
    def get_all_claimer_names(self, receipt_id: str) -> List[str]:
        """Get all unique claimer names for a receipt"""
        names = Claim.objects.filter(
            line_item__receipt_id=receipt_id
        ).values_list('claimer_name', flat=True).distinct()
        
        return list(names)