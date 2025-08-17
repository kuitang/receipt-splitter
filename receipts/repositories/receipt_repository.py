"""
Repository for Receipt data access
Encapsulates all database queries related to receipts
"""
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.db.models import QuerySet, Prefetch, Sum, F
from django.utils import timezone

from receipts.models import Receipt, LineItem, Claim


class ReceiptRepository:
    """Handles all data access for receipts"""
    
    def get_by_id(self, receipt_id: str) -> Optional[Receipt]:
        """Get receipt by ID with related items"""
        try:
            receipt = Receipt.objects.select_related().prefetch_related('items').get(id=receipt_id)
            # Ensure slug exists (for legacy receipts created without slug)
            if not receipt.slug:
                receipt.slug = Receipt.generate_unique_slug()
                receipt.save(update_fields=['slug'])
            return receipt
        except Receipt.DoesNotExist:
            return None
    
    def get_by_slug(self, slug: str) -> Optional[Receipt]:
        """Get receipt by slug with related items"""
        try:
            return Receipt.objects.select_related().prefetch_related('items').get(slug=slug)
        except Receipt.DoesNotExist:
            return None
    
    def get_with_claims_and_viewers(self, receipt_id: str) -> Optional[Receipt]:
        """Get receipt with all related data optimized"""
        try:
            receipt = Receipt.objects.prefetch_related(
                'items',
                'viewers',
                Prefetch('items__claims', 
                         queryset=Claim.objects.select_related('line_item'))
            ).get(id=receipt_id)
            
            # Ensure slug exists (for legacy receipts)
            if not receipt.slug:
                receipt.slug = Receipt.generate_unique_slug()
                receipt.save(update_fields=['slug'])
            
            return receipt
        except Receipt.DoesNotExist:
            return None
    
    def get_expired_receipts(self, before_date: Optional[datetime] = None) -> QuerySet:
        """Get all expired receipts for cleanup"""
        if before_date is None:
            before_date = timezone.now()
        return Receipt.objects.filter(expires_at__lt=before_date)
    
    @transaction.atomic
    def create_receipt(self, data: Dict) -> Receipt:
        """Create receipt with optional items in a transaction"""
        items_data = data.pop('items', [])
        
        receipt = Receipt.objects.create(**data)
        
        for item_data in items_data:
            line_item = LineItem.objects.create(
                receipt=receipt,
                **item_data
            )
            line_item.calculate_prorations()
            line_item.save()
        
        return receipt
    
    def update_receipt_fields(self, receipt_id: str, **fields) -> bool:
        """Update specific receipt fields efficiently"""
        updated = Receipt.objects.filter(id=receipt_id).update(**fields)
        return updated > 0
    
    @transaction.atomic
    def update_receipt_with_items(self, receipt: Receipt, data: Dict) -> Receipt:
        """Update receipt and replace all items atomically"""
        # Update receipt fields
        for field, value in data.items():
            if field != 'items' and hasattr(receipt, field):
                setattr(receipt, field, value)
        receipt.save()
        
        # Replace items if provided
        if 'items' in data:
            # Delete existing items
            receipt.items.all().delete()
            
            # Create new items
            for item_data in data['items']:
                line_item = LineItem.objects.create(
                    receipt=receipt,
                    **item_data
                )
                line_item.calculate_prorations()
                line_item.save()
        
        return receipt
    
    def finalize_receipt(self, receipt_id: str) -> bool:
        """Mark receipt as finalized"""
        updated = Receipt.objects.filter(
            id=receipt_id,
            is_finalized=False
        ).update(is_finalized=True)
        return updated > 0
    
    def is_receipt_finalized(self, receipt_id: str) -> bool:
        """Check if receipt is finalized"""
        try:
            return Receipt.objects.filter(
                id=receipt_id,
                is_finalized=True
            ).exists()
        except:
            return False
    
    def get_receipt_data_for_validation(self, receipt: Receipt) -> Dict:
        """Get receipt data in format needed for validation"""
        return {
            'restaurant_name': receipt.restaurant_name,
            'subtotal': str(receipt.subtotal),
            'tax': str(receipt.tax),
            'tip': str(receipt.tip),
            'total': str(receipt.total),
            'items': [
                {
                    'name': item.name,
                    'quantity': item.quantity,
                    'unit_price': str(item.unit_price),
                    'total_price': str(item.total_price)
                }
                for item in receipt.items.all()
            ]
        }
    
    def delete_expired_receipts(self, before_date: Optional[datetime] = None) -> int:
        """Delete expired receipts and return count deleted"""
        if before_date is None:
            before_date = timezone.now()
        
        expired = self.get_expired_receipts(before_date)
        count = expired.count()
        expired.delete()
        return count