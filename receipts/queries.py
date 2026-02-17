"""
Derived state queries for receipts.
These compute boolean flags from existing data without adding new DB fields.
"""

from .models import Receipt, ReceiptOCRResult


def receipt_state(receipt):
    """Returns a dict of boolean flags for one receipt."""
    is_corrected = (
        hasattr(receipt, 'ocr_result') and receipt.ocr_result.is_corrected()
    )
    all_items = receipt.items.all()
    fully_claimed = all(
        sum(c.quantity_numerator for c in item.claims.all()) >= item.quantity_numerator
        for item in all_items
    ) if all_items.exists() else False
    return {
        'finalized': receipt.is_finalized,
        'fully_claimed': fully_claimed,
        'corrected': is_corrected,
        'has_ocr': hasattr(receipt, 'ocr_result'),
        'abandoned': not receipt.is_finalized,
    }


def deletable_receipts_qs():
    """Finalized, uncorrected, older than 30 days — safe to delete."""
    from datetime import timedelta
    from django.utils import timezone
    cutoff = timezone.now() - timedelta(days=30)
    corrected_ids = [
        r.receipt_id for r in ReceiptOCRResult.objects.select_related('receipt')
        if r.is_corrected()
    ]
    return Receipt.objects.filter(
        is_finalized=True,
        created_at__lt=cutoff,
    ).exclude(id__in=corrected_ids)
