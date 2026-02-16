"""
Mock OCR module for integration testing.
Controls whether to use real Gemini API or mock data via environment variable.
"""

import os
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Environment variable to control OCR behavior
USE_REAL_OCR = os.environ.get('INTEGRATION_TEST_REAL_OPENAI_OCR', 'false').lower() == 'true'

if USE_REAL_OCR:
    logger.info("USING REAL GEMINI API FOR OCR (costs money!)")
else:
    logger.info("USING MOCK OCR DATA (no API calls)")


class MockReceiptData:
    """Mock receipt data for different test scenarios"""

    @staticmethod
    def get_default_receipt():
        """Default receipt with balanced totals"""
        return {
            "restaurant_name": "Test Restaurant",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "items": [
                {"name": "Burger", "quantity": 1, "unit_price": 12.99, "total_price": 12.99},
                {"name": "Fries", "quantity": 2, "unit_price": 4.50, "total_price": 9.00},
                {"name": "Soda", "quantity": 1, "unit_price": 3.50, "total_price": 3.50},
            ],
            "subtotal": 25.49,
            "tax": 2.16,
            "tip": 0.00,
            "total": 27.65,
            "confidence_score": 0.95,
            "notes": "Mock OCR data"
        }

    @staticmethod
    def get_unbalanced_receipt():
        """Receipt with incorrect totals for testing validation"""
        return {
            "restaurant_name": "Unbalanced Cafe",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "items": [
                {"name": "Pizza", "quantity": 1, "unit_price": 15.00, "total_price": 15.00},
                {"name": "Salad", "quantity": 1, "unit_price": 8.00, "total_price": 8.00},
            ],
            "subtotal": 25.00,  # Wrong - should be 23.00
            "tax": 2.00,
            "tip": 3.00,
            "total": 30.00,
            "confidence_score": 0.80,
            "notes": "Mock OCR data with balance issues"
        }

    @staticmethod
    def get_large_receipt():
        """Large receipt with many items"""
        items = []
        subtotal = Decimal('0')
        for i in range(20):
            price = Decimal(f"{5 + i}.99")
            items.append({
                "name": f"Item {i+1}",
                "quantity": 1,
                "unit_price": float(price),
                "total_price": float(price)
            })
            subtotal += price

        tax = subtotal * Decimal('0.08')
        tip = subtotal * Decimal('0.18')
        total = subtotal + tax + tip

        return {
            "restaurant_name": "Big Order Restaurant",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "items": items,
            "subtotal": float(subtotal),
            "tax": float(tax.quantize(Decimal('0.01'))),
            "tip": float(tip.quantize(Decimal('0.01'))),
            "total": float(total.quantize(Decimal('0.01'))),
            "confidence_score": 0.92,
            "notes": "Mock OCR data with many items"
        }

    @staticmethod
    def get_minimal_receipt():
        """Minimal receipt with single item"""
        return {
            "restaurant_name": "Quick Snack",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "items": [
                {"name": "Coffee", "quantity": 1, "unit_price": 4.50, "total_price": 4.50},
            ],
            "subtotal": 4.50,
            "tax": 0.36,
            "tip": 0.00,
            "total": 4.86,
            "confidence_score": 0.99,
            "notes": "Mock OCR data - minimal"
        }

    @staticmethod
    def get_receipt_by_filename(filename: str) -> Dict[str, Any]:
        """Return different mock data based on filename for testing variety"""
        filename_lower = filename.lower()

        if 'unbalanced' in filename_lower:
            return MockReceiptData.get_unbalanced_receipt()
        elif 'large' in filename_lower or 'many' in filename_lower:
            return MockReceiptData.get_large_receipt()
        elif 'minimal' in filename_lower or 'simple' in filename_lower:
            return MockReceiptData.get_minimal_receipt()
        else:
            return MockReceiptData.get_default_receipt()


def patch_ocr_for_tests():
    """
    Patch the OCR service to use mock data or real API based on environment variable.
    Returns a context manager for use in tests.
    """
    from unittest.mock import patch, MagicMock
    from lib.ocr import ReceiptData, LineItem as OCRLineItem

    def mock_process_image_bytes(self, image_bytes, format="JPEG"):
        """Mock implementation of process_image_bytes"""
        if USE_REAL_OCR:
            # Call the real method
            return self._original_process_image_bytes(image_bytes, format)

        # Use mock data
        logger.info("Using mock OCR data (no API call)")

        # Determine which mock data to use based on image size
        image_size = len(image_bytes)

        if image_size < 100:
            data = MockReceiptData.get_minimal_receipt()
        elif image_size < 1000:
            data = MockReceiptData.get_default_receipt()
        elif image_size < 5000:
            data = MockReceiptData.get_unbalanced_receipt()
        else:
            data = MockReceiptData.get_large_receipt()

        # Convert to ReceiptData object
        items = []
        for item_data in data['items']:
            items.append(OCRLineItem(
                name=item_data['name'],
                quantity=item_data['quantity'],
                unit_price=Decimal(str(item_data['unit_price'])),
                total_price=Decimal(str(item_data['total_price']))
            ))

        return ReceiptData(
            restaurant_name=data['restaurant_name'],
            date=datetime.strptime(data['date'], '%Y-%m-%d'),
            items=items,
            subtotal=Decimal(str(data['subtotal'])),
            tax=Decimal(str(data['tax'])),
            tip=Decimal(str(data['tip'])),
            total=Decimal(str(data['total'])),
            confidence_score=data['confidence_score'],
            notes=data.get('notes', 'Mock OCR response')
        )

    def mock_process_image(self, image_path):
        """Mock implementation of process_image"""
        if USE_REAL_OCR:
            # Call the real method
            return self._original_process_image(image_path)

        # Use mock data based on filename
        logger.info(f"Using mock OCR data for {image_path} (no API call)")
        filename = str(image_path)
        data = MockReceiptData.get_receipt_by_filename(filename)

        # Convert to ReceiptData object
        items = []
        for item_data in data['items']:
            items.append(OCRLineItem(
                name=item_data['name'],
                quantity=item_data['quantity'],
                unit_price=Decimal(str(item_data['unit_price'])),
                total_price=Decimal(str(item_data['total_price']))
            ))

        return ReceiptData(
            restaurant_name=data['restaurant_name'],
            date=datetime.strptime(data['date'], '%Y-%m-%d'),
            items=items,
            subtotal=Decimal(str(data['subtotal'])),
            tax=Decimal(str(data['tax'])),
            tip=Decimal(str(data['tip'])),
            total=Decimal(str(data['total'])),
            confidence_score=data['confidence_score'],
            notes=data.get('notes', 'Mock OCR response')
        )

    # Create patches
    patches = []

    # Patch ReceiptOCR.__init__ to skip API key requirement when mocking
    if not USE_REAL_OCR:
        def mock_init(self, api_key=None, model="gemini-3-flash-preview", thinking_level="low"):
            self.model = model
            self.thinking_level = thinking_level
            # Don't initialize Gemini client when mocking
            self.client = None
            logger.info("Initialized MockReceiptOCR (no Gemini client)")

        patches.append(patch('lib.ocr.ReceiptOCR.__init__', mock_init))

    # Patch the processing methods
    patches.append(patch('lib.ocr.ReceiptOCR.process_image_bytes', mock_process_image_bytes))
    patches.append(patch('lib.ocr.ReceiptOCR.process_image', mock_process_image))

    # Store original methods if using real OCR
    if USE_REAL_OCR:
        from lib.ocr import ReceiptOCR
        ReceiptOCR._original_process_image_bytes = ReceiptOCR.process_image_bytes
        ReceiptOCR._original_process_image = ReceiptOCR.process_image

    return patches


def get_ocr_status():
    """Return current OCR mock status"""
    return {
        "using_real_ocr": USE_REAL_OCR,
        "status_message": "Using Real Gemini API" if USE_REAL_OCR else "Using Mock OCR Data",
        "env_var": "INTEGRATION_TEST_REAL_OPENAI_OCR",
        "env_value": os.environ.get('INTEGRATION_TEST_REAL_OPENAI_OCR', 'false')
    }
