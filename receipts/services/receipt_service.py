"""
Service layer for receipt operations
Encapsulates all business logic related to receipts
"""
from typing import Dict, Optional, Tuple, List
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.signing import Signer, BadSignature
from django.core.cache import cache
from django.db import transaction
from django.db.models import QuerySet, Prefetch, Sum, F, DecimalField, FloatField
from django.db.models.functions import Cast

from receipts.models import Receipt, LineItem, ActiveViewer, Claim
from receipts.services.validation_pipeline import ValidationPipeline
from receipts.async_processor import (
    process_receipt_async,
    process_receipt_sync,
    create_placeholder_receipt,
)
from receipts.image_storage import store_receipt_image_in_memory, delete_receipt_image_from_memory


class ReceiptNotFoundError(Exception):
    pass


class ReceiptAlreadyFinalizedError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


class ReceiptService:
    """Handles all business logic for receipts"""
    
    def __init__(self):
        self.validator = ValidationPipeline()
        self.signer = Signer()
    
    def create_receipt(self, uploader_name: str, image_file, venmo_username: str = '') -> Receipt:
        """
        Create a new receipt with async OCR processing
        """
        # Validate inputs
        validated_name = self.validator.validate_name(uploader_name, "Your name")
        validated_image = self.validator.validate_image_file(image_file)

        # Create placeholder receipt
        receipt = create_placeholder_receipt(validated_name, validated_image, venmo_username=venmo_username)
        
        # Start OCR processing according to configuration
        if getattr(settings, "USE_ASYNC_PROCESSING", True):
            process_receipt_async(receipt.id, validated_image)
        else:
            process_receipt_sync(receipt.id, validated_image)

        return receipt
    
    def get_receipt_by_id(self, receipt_id: str) -> Optional[Receipt]:
        """Get receipt by ID"""
        return self._get_by_id(receipt_id)
    
    def get_receipt_by_slug(self, slug: str) -> Optional[Receipt]:
        """Get receipt by slug"""
        return self._get_by_slug(slug)
    
    def update_receipt(self, receipt_id: str, data: Dict, 
                      session_context: Dict) -> Dict:
        """
        Update receipt with validation
        Allows saving even if data doesn't balance (business requirement)
        """
        # Get receipt
        receipt = self._get_by_id(receipt_id)
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
                    'quantity_numerator': item.get('quantity_numerator', item.get('quantity', 1)),
                    'quantity_denominator': item.get('quantity_denominator', 1),
                    'unit_price': Decimal(str(item['unit_price'])),
                    'total_price': Decimal(str(item['total_price']))
                }
                for item in validated_data['items']
            ]
        
        # Update through repository
        updated_receipt = self._update_receipt_with_items(receipt, update_data)
        
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
        receipt = self._get_by_id(receipt_id)
        if not receipt:
            raise ReceiptNotFoundError(f"Receipt {receipt_id} not found")
        
        # Check if already finalized
        if receipt.is_finalized:
            raise ReceiptAlreadyFinalizedError("Receipt is already finalized")
        
        # Check permission (only uploader can finalize)
        if not session_context.get('is_uploader'):
            raise PermissionDeniedError("Only the uploader can finalize the receipt")
        
        # Get receipt data for validation
        receipt_data = self._get_receipt_data_for_validation(receipt)
        
        # Strict validation for finalization
        is_valid, validation_errors = self.validator.validate_for_finalization(receipt_data)
        
        if not is_valid:
            error_message = "Receipt doesn't balance. Please fix the following issues:\n"
            error_message += self.validator.format_validation_errors(validation_errors)
            
            raise ValidationError(error_message, params={
                'validation_errors': validation_errors
            })
        
        # Finalize the receipt
        self._finalize_receipt(receipt_id)
        
        # Delete the image from memory
        delete_receipt_image_from_memory(receipt_id)

        return {
            'success': True,
            'share_url': receipt.get_absolute_url()
        }
    
    def get_receipt_for_viewing_by_slug(self, slug: str) -> Dict:
        """
        Get receipt by slug with all claims and calculations for viewing
        Combines get_receipt_by_slug and get_receipt_for_viewing into ONE query
        """
        # Try cache first for finalized receipts
        # We need to get ID first, but we can do it in the same query below
        
        # Get receipt with ALL related data in ONE query!
        try:
            receipt = Receipt.objects.prefetch_related(
                'items',
                'viewers',
                Prefetch('items__claims', 
                         queryset=Claim.objects.select_related('line_item'))
            ).get(slug=slug)
            
            # Ensure slug exists (for legacy receipts)
            if not receipt.slug:
                receipt.slug = Receipt.generate_unique_slug()
                receipt.save(update_fields=['slug'])
        except Receipt.DoesNotExist:
            raise ReceiptNotFoundError(f"Receipt with slug {slug} not found")
        
        # Check cache for finalized receipts
        cache_key = f"receipt_view:{receipt.id}"
        if receipt.is_finalized:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        
        # Rest of the method remains the same...
        return self._prepare_receipt_viewing_data(receipt)
    
    def get_receipt_for_viewing(self, receipt_id: str) -> Dict:
        """
        Get receipt with all claims and calculations for viewing
        Uses cache for finalized receipts
        """
        # Check cache for finalized receipts
        cache_key = f"receipt_view:{receipt_id}"
        
        # Get receipt with all related data in ONE query (not two!)
        receipt = self._get_with_claims_and_viewers(receipt_id)
        if not receipt:
            raise ReceiptNotFoundError(f"Receipt {receipt_id} not found")
        
        # Check cache AFTER we have the receipt (avoid double query)
        if receipt.is_finalized:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        
        return self._prepare_receipt_viewing_data(receipt)
    
    def _prepare_receipt_viewing_data(self, receipt: Receipt) -> Dict:
        """Prepare viewing data from a prefetched receipt (no additional queries!)"""
        receipt_id = str(receipt.id)
        
        # Prepare items with claims data - calculate availability without extra queries!
        items_with_claims = []
        for item in receipt.items.all():
            claims = item.claims.all()  # Already prefetched, no query!
            # Calculate available quantity from prefetched data (shared denominator)
            total_claimed_num = sum(claim.quantity_numerator for claim in claims)
            available_quantity = item.quantity_numerator - total_claimed_num
            
            items_with_claims.append({
                'item': item,
                'claims': claims,
                'available_quantity': available_quantity
            })
        
        # Calculate participant totals
        participant_totals = self._get_participant_totals(receipt_id)
        
        # Calculate summary
        total_claimed = sum(participant_totals.values())
        total_unclaimed = receipt.total - total_claimed
        
        # Build name→venmo map from prefetched viewers
        viewer_venmo_map = {
            v.viewer_name: v.venmo_username
            for v in receipt.viewers.all()
            if v.venmo_username
        }

        # Sort participants by name, include venmo if available
        participant_list = sorted([
            {'name': name, 'amount': amount,
             'venmo_username': viewer_venmo_map.get(name, '')}
            for name, amount in participant_totals.items()
        ], key=lambda x: x['name'])
        
        result = {
            'receipt': receipt,
            'items_with_claims': items_with_claims,
            'participant_totals': participant_list,
            'total_claimed': total_claimed,
            'total_unclaimed': total_unclaimed
        }
        
        # Cache if finalized (30 minutes)
        cache_key = f"receipt_view:{receipt_id}"
        if receipt.is_finalized:
            cache.set(cache_key, result, 1800)
        
        return result
    
    def register_viewer(self, receipt_id: str, viewer_name: str, session_id: str,
                        venmo_username: str = '') -> ActiveViewer:
        """Register a viewer for the receipt"""
        receipt = self._get_by_id(receipt_id)
        if not receipt:
            raise ReceiptNotFoundError(f"Receipt {receipt_id} not found")

        viewer, created = ActiveViewer.objects.update_or_create(
            receipt=receipt,
            session_id=session_id,
            defaults={'viewer_name': viewer_name, 'venmo_username': venmo_username}
        )

        return viewer
    
    def get_existing_names(self, receipt_id: str, receipt_data: Optional[Dict] = None) -> list:
        """Get all existing viewer and claimer names for a receipt
        
        Args:
            receipt_id: The receipt ID
            receipt_data: Optional pre-fetched receipt data to avoid extra queries
        """
        if receipt_data:
            # Use pre-fetched data to avoid extra queries
            receipt = receipt_data.get('receipt')
            if not receipt:
                return []
            
            names = []
            # Add uploader name
            names.append(receipt.uploader_name)
            
            # Add viewer names from prefetched viewers (use .all() to avoid extra query)
            if hasattr(receipt, 'viewers'):
                names.extend([viewer.viewer_name for viewer in receipt.viewers.all()])
            
            # Extract claimer names from items_with_claims data
            if 'items_with_claims' in receipt_data:
                for item_data in receipt_data['items_with_claims']:
                    for claim in item_data.get('claims', []):
                        names.append(claim.claimer_name)
            
            return list(set(names))  # Remove duplicates
        else:
            # Fallback to fetching from database
            receipt = self._get_with_claims_and_viewers(receipt_id)
            if not receipt:
                return []
            
            names = list(receipt.viewers.values_list('viewer_name', flat=True))
            names.extend(self._get_all_claimer_names(receipt_id))
            # Include the uploader's name in collision check
            names.append(receipt.uploader_name)
            
            return list(set(names))  # Remove duplicates
    
    def create_edit_token(self, receipt_id: str, session_key: str) -> str:
        """Create a secure edit token for a receipt"""
        data = f"{receipt_id}:{session_key}"
        return self.signer.sign(data)
    
    def _verify_edit_permission(self, receipt: Receipt, session_context: Dict) -> bool:
        """Verify if user has permission to edit receipt"""
        if receipt.is_finalized:
            return False
        
        # Check if user is the uploader (new session system)
        if session_context.get('is_uploader'):
            return True
        
        # Check for edit token
        stored_token = session_context.get('edit_token')
        if not stored_token:
            return False
        
        try:
            unsigned = self.signer.unsign(stored_token)
            receipt_id, session_key = unsigned.split(':')
            return (str(receipt.id) == receipt_id and 
                   session_context.get('session_key') == session_key)
        except (BadSignature, ValueError):
            return False
    
    # Private methods (formerly in ReceiptRepository)
    
    def _get_by_id(self, receipt_id: str) -> Optional[Receipt]:
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
    
    def _get_by_slug(self, slug: str) -> Optional[Receipt]:
        """Get receipt by slug with related items"""
        try:
            return Receipt.objects.select_related().prefetch_related('items').get(slug=slug)
        except Receipt.DoesNotExist:
            return None
    
    def _get_with_claims_and_viewers(self, receipt_id: str) -> Optional[Receipt]:
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
    
    @transaction.atomic
    def _update_receipt_with_items(self, receipt: Receipt, data: Dict) -> Receipt:
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
            
            # Calculate prorations in memory and prepare bulk create
            items_to_create = []
            for item_data in data['items']:
                line_item = LineItem(
                    receipt=receipt,
                    **item_data
                )
                # Calculate prorations in memory (no DB access needed)
                line_item.calculate_prorations()
                items_to_create.append(line_item)
            
            # Single bulk insert for all items
            LineItem.objects.bulk_create(items_to_create)
        
        return receipt
    
    def _finalize_receipt(self, receipt_id: str) -> bool:
        """Mark receipt as finalized"""
        updated = Receipt.objects.filter(
            id=receipt_id,
            is_finalized=False
        ).update(is_finalized=True)
        return updated > 0
    
    def _get_receipt_data_for_validation(self, receipt: Receipt) -> Dict:
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
                    'quantity_numerator': item.quantity_numerator,
                    'quantity_denominator': item.quantity_denominator,
                    'unit_price': str(item.unit_price),
                    'total_price': str(item.total_price)
                }
                for item in receipt.items.all()
            ]
        }
    
    def _get_participant_totals(self, receipt_id: str) -> Dict[str, Decimal]:
        """Calculate totals per participant efficiently using single database query.

        Share = (claim.numerator / item.numerator) * (item.total + item.tax + item.tip)
        """
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
    
    def _get_all_claimer_names(self, receipt_id: str) -> List[str]:
        """Get all unique claimer names for a receipt"""
        names = Claim.objects.filter(
            line_item__receipt_id=receipt_id
        ).values_list('claimer_name', flat=True).distinct()
        
        return list(names)