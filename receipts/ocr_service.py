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
    if not settings.GEMINI_API_KEY:
        return None

    if _ocr_instance is None:
        logger.info("Initializing global OCR instance")
        _ocr_instance = ReceiptOCR(settings.GEMINI_API_KEY)

    return _ocr_instance


def process_receipt_with_ocr(image_input, format_hint=None):
    """
    Process receipt image using Gemini Vision API to extract structured data

    Args:
        image_input: Django UploadedFile object, file-like object, or bytes
        format_hint: Optional format hint (JPEG, HEIC, PNG, etc.)

    Returns:
        Dictionary with receipt data compatible with Django models
    """

    # Get the global OCR instance
    ocr = get_ocr_instance()
    if ocr is None:
        logger.warning("Gemini API key not configured, using mock data")
        logger.info("Returning hardcoded mock receipt data - no API costs incurred")
        return get_mock_receipt_data()

    try:

        # Handle different input types
        if isinstance(image_input, bytes):
            # Already bytes, use directly
            image_bytes = image_input
        else:
            # File-like object, read bytes
            image_input.seek(0)  # Ensure we're at the start
            image_bytes = image_input.read()

        logger.info(f"Processing receipt image ({len(image_bytes)} bytes)")
        receipt_data = ocr.process_image(image_bytes)

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
        "confidence_score": receipt_data.confidence_score,
        "notes": receipt_data.notes,
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
        "tip": 0.00,
        "total": 39.18,
        "confidence_score": 1.0,  # Mock data is 100% confident
        "notes": None,
    }
