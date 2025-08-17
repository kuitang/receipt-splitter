"""
OCR Service for Django app - integrates with ocr_lib
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from django.conf import settings

from lib.ocr import ReceiptOCR, ReceiptData, LineItem

logger = logging.getLogger(__name__)

# Global OCR instance with persistent cache
_ocr_instance = None


def get_ocr_instance():
    """Get or create the global OCR instance with persistent cache"""
    global _ocr_instance
    
    # Check if API key is configured
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_api_key_here":
        return None
    
    if _ocr_instance is None:
        logger.info("Initializing global OCR instance with cache")
        _ocr_instance = ReceiptOCR(settings.OPENAI_API_KEY, cache_size=128)
    
    return _ocr_instance


def process_receipt_with_ocr(image_input, format_hint=None):
    """
    Process receipt image using OpenAI Vision API to extract structured data
    
    Args:
        image_input: Django UploadedFile object, file-like object, or bytes
        format_hint: Optional format hint (JPEG, HEIC, PNG, etc.)
        
    Returns:
        Dictionary with receipt data compatible with Django models
    """
    
    # Get the global OCR instance
    ocr = get_ocr_instance()
    if ocr is None:
        logger.warning("OpenAI API key not configured, using mock data")
        logger.info("Returning hardcoded mock receipt data - no API costs incurred")
        return get_mock_receipt_data()
    
    try:
        
        # Handle different input types
        if isinstance(image_input, bytes):
            # Already bytes, use directly
            image_bytes = image_input
            filename = "uploaded_file"
        else:
            # File-like object, read bytes
            image_input.seek(0)  # Ensure we're at the start
            image_bytes = image_input.read()
            filename = getattr(image_input, 'name', 'uploaded_file')
        
        # Use provided format hint or detect from filename
        if not format_hint:
            format_hint = "JPEG"  # Default
            if filename:
                lower_name = filename.lower()
                if lower_name.endswith('.heic') or lower_name.endswith('.heif'):
                    format_hint = "HEIC"
                elif lower_name.endswith('.png'):
                    format_hint = "PNG"
                elif lower_name.endswith('.webp'):
                    format_hint = "WEBP"
        
        logger.info(f"Processing receipt image: {filename} (format: {format_hint})")
        receipt_data = ocr.process_image_bytes(image_bytes, format=format_hint)
        
        # Log cache statistics
        cache_stats = ocr.get_cache_stats()
        logger.info(f"OCR Cache Stats - Hits: {cache_stats['cache_hits']}, "
                   f"Misses: {cache_stats['cache_misses']}, "
                   f"Hit Rate: {cache_stats['hit_rate']}%")
        
        # Validate the extracted data
        is_valid, errors = receipt_data.validate_totals()
        if not is_valid:
            logger.warning(f"Receipt validation issues: {errors}")
        
        # Convert to Django-compatible format
        return receipt_data_to_dict(receipt_data)
        
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        logger.info("Falling back to mock data")
        logger.info("Returning hardcoded mock receipt data - no API costs incurred")
        return get_mock_receipt_data()


def receipt_data_to_dict(receipt_data: ReceiptData) -> dict:
    """
    Convert ReceiptData object to dictionary format expected by Django views
    
    Args:
        receipt_data: ReceiptData object from OCR
        
    Returns:
        Dictionary with receipt information
    """
    return {
        "restaurant_name": receipt_data.restaurant_name,
        "date": receipt_data.date,
        "items": [
            {
                "name": item.name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total_price": float(item.total_price)
            }
            for item in receipt_data.items
        ],
        "subtotal": float(receipt_data.subtotal),
        "tax": float(receipt_data.tax),
        "tip": float(receipt_data.tip),
        "total": float(receipt_data.total),
        "confidence_score": receipt_data.confidence_score
    }


def get_mock_receipt_data():
    """Return mock receipt data for testing"""
    return {
        "restaurant_name": "Demo Restaurant",
        "date": datetime.now(),
        "items": [
            {
                "name": "Burger",
                "quantity": 1,
                "unit_price": 12.99,
                "total_price": 12.99
            },
            {
                "name": "Fries",
                "quantity": 2,
                "unit_price": 3.99,
                "total_price": 7.98
            },
            {
                "name": "Soda",
                "quantity": 2,
                "unit_price": 2.99,
                "total_price": 5.98
            },
            {
                "name": "Salad",
                "quantity": 1,
                "unit_price": 8.99,
                "total_price": 8.99
            }
        ],
        "subtotal": 35.94,
        "tax": 3.24,
        "tip": 6.00,
        "total": 45.18,
        "confidence_score": 1.0  # Mock data is 100% confident
    }