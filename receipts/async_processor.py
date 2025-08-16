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

logger = logging.getLogger(__name__)


def process_receipt_async(receipt_id, image_file):
    """
    Process receipt OCR in a background thread
    
    Args:
        receipt_id: UUID of the receipt to process
        image_file: The uploaded image file
    """
    # Read the file content before starting the thread
    # to avoid file being closed before the thread can read it
    image_file.seek(0)
    image_content = image_file.read()
    image_file.seek(0)
    
    thread = threading.Thread(
        target=_process_receipt_worker,
        args=(receipt_id, image_content),
        daemon=True
    )
    thread.start()
    logger.info(f"Started async OCR processing for receipt {receipt_id}")


def _process_receipt_worker(receipt_id, image_content):
    """
    Worker function that runs in background thread
    
    Args:
        receipt_id: UUID of the receipt to process
        image_content: The image file content as bytes
    """
    try:
        # Get the receipt
        receipt = Receipt.objects.get(id=receipt_id)
        
        # Update status to processing
        receipt.processing_status = 'processing'
        receipt.save(update_fields=['processing_status'])
        logger.info(f"Processing receipt {receipt_id}")
        
        # Process with OCR
        ocr_data = process_receipt_with_ocr(image_content)
        
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
        logger.error(f"Error processing receipt {receipt_id}: {str(e)}")
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            receipt.processing_status = 'failed'
            receipt.processing_error = str(e)
            receipt.save(update_fields=['processing_status', 'processing_error'])
        except:
            pass  # Can't update receipt status


def create_placeholder_receipt(uploader_name, image):
    """
    Create a placeholder receipt that will be processed async
    
    Args:
        uploader_name: Name of the uploader
        image: The uploaded image file
        
    Returns:
        Receipt object
    """
    receipt = Receipt.objects.create(
        uploader_name=uploader_name,
        restaurant_name="Processing...",
        date=timezone.now(),
        subtotal=Decimal('0'),
        tax=Decimal('0'),
        tip=Decimal('0'),
        total=Decimal('0'),
        image=image,
        processing_status='pending'
    )
    
    # Create a single placeholder item
    LineItem.objects.create(
        receipt=receipt,
        name="Analyzing your receipt...",
        quantity=1,
        unit_price=Decimal('0'),
        total_price=Decimal('0')
    )
    
    return receipt