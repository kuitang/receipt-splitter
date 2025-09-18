"""
Async processor for receipt OCR
Handles background processing of uploaded receipts
"""

import logging
import threading
from decimal import Decimal
from django.utils import timezone
from .models import Receipt, LineItem
from .ocr_service import process_receipt_with_ocr
from .image_utils import convert_to_jpeg_if_needed, get_image_bytes_for_ocr
from .image_storage import store_receipt_image_in_memory

logger = logging.getLogger(__name__)


def process_receipt_async(receipt_id, original_image_file):
    """
    Process receipt OCR in a background thread
    
    Args:
        receipt_id: UUID of the receipt to process
        original_image_file: The original uploaded image file (might be HEIC)
    """
    # Get the image bytes for OCR (handles HEIC)
    # Note: We pass the original HEIC to OCR, but store as JPEG
    image_bytes, format_hint = get_image_bytes_for_ocr(original_image_file)
    
    thread = threading.Thread(
        target=_process_receipt_worker,
        args=(receipt_id, image_bytes, format_hint),
        daemon=True
    )
    thread.start()
    logger.info(f"Started async OCR processing for receipt {receipt_id}")


def process_receipt_sync(receipt_id, original_image_file):
    """Process receipt OCR synchronously (used when async is disabled in tests)."""
    image_bytes, format_hint = get_image_bytes_for_ocr(original_image_file)
    _process_receipt_worker(receipt_id, image_bytes, format_hint)


def _process_receipt_worker(receipt_id, image_content, format_hint="JPEG"):
    """
    Worker function that runs in background thread
    
    Args:
        receipt_id: UUID of the receipt to process
        image_content: The image file content as bytes
        format_hint: Format hint for OCR (JPEG, HEIC, PNG, etc.)
    """
    try:
        # Get the receipt
        receipt = Receipt.objects.get(id=receipt_id)
        
        # Update status to processing
        receipt.processing_status = 'processing'
        receipt.save(update_fields=['processing_status'])
        logger.info(f"Processing receipt {receipt_id}")
        
        # Process with OCR (pass format hint for proper handling)
        ocr_data = process_receipt_with_ocr(image_content, format_hint=format_hint)
        
        # Update receipt with OCR data
        receipt.restaurant_name = ocr_data['restaurant_name']
        receipt.date = ocr_data['date']
        receipt.subtotal = Decimal(str(ocr_data['subtotal']))
        receipt.tax = Decimal(str(ocr_data['tax']))
        receipt.tip = Decimal(str(ocr_data['tip']))
        receipt.total = Decimal(str(ocr_data['total']))
        receipt.processing_status = 'completed'
        receipt.save()
        
        # Delete existing placeholder items
        receipt.items.all().delete()
        
        # Create line items from OCR data
        for item_data in ocr_data['items']:
            line_item = LineItem.objects.create(
                receipt=receipt,
                name=item_data['name'],
                quantity=item_data['quantity'],
                unit_price=Decimal(str(item_data['unit_price'])),
                total_price=Decimal(str(item_data['total_price']))
            )
            line_item.calculate_prorations()
            line_item.save()
        
        logger.info(f"Successfully processed receipt {receipt_id}: {receipt.restaurant_name}")
        
    except Receipt.DoesNotExist:
        logger.error(f"Receipt {receipt_id} not found")
        
    except Exception as e:
        logger.exception(f"Error processing receipt {receipt_id}")
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            receipt.processing_status = 'failed'
            receipt.processing_error = "An unexpected error occurred during processing."
            receipt.save(update_fields=['processing_status', 'processing_error'])
        except Exception as update_e:
            logger.error(f"Failed to update receipt status for {receipt_id}: {update_e}")


def create_placeholder_receipt(uploader_name, image):
    """
    Create a placeholder receipt that will be processed async
    Stores image in memory for browser display
    
    Args:
        uploader_name: Name of the uploader
        image: The uploaded image file (may be HEIC)
        
    Returns:
        Receipt object
    """
    # Convert HEIC to JPEG if needed (for browser display)
    converted_image = convert_to_jpeg_if_needed(image)
    
    receipt = Receipt.objects.create(
        uploader_name=uploader_name,
        restaurant_name="Processing...",
        date=timezone.now(),
        subtotal=Decimal('0'),
        tax=Decimal('0'),
        tip=Decimal('0'),
        total=Decimal('0'),
        # Don't save image to disk
        processing_status='pending'
    )
    
    # Store the converted image in memory
    store_receipt_image_in_memory(receipt.id, converted_image)
    
    # Create a single placeholder item
    LineItem.objects.create(
        receipt=receipt,
        name="Analyzing your receipt...",
        quantity=1,
        unit_price=Decimal('0'),
        total_price=Decimal('0')
    )
    
    return receipt