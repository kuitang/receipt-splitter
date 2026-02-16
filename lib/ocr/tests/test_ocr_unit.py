#!/usr/bin/env python3
"""
Unit tests for OCR library interface
Tests the API without making actual Gemini calls
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import json

import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.ocr.ocr_lib import ReceiptOCR
from lib.ocr.models import ReceiptData, LineItem


class TestLineItem(unittest.TestCase):
    """Test LineItem Pydantic model"""

    def test_line_item_creation(self):
        item = LineItem(
            name="Test Item",
            quantity=2,
            unit_price=Decimal("10.50"),
            total_price=Decimal("21.00")
        )

        self.assertEqual(item.name, "Test Item")
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("10.50"))
        self.assertEqual(item.total_price, Decimal("21.00"))

    def test_line_item_to_dict(self):
        item = LineItem(
            name="Test Item",
            quantity=1,
            unit_price=Decimal("5.99"),
            total_price=Decimal("5.99")
        )

        result = item.to_dict()
        self.assertEqual(result['name'], "Test Item")
        self.assertEqual(result['quantity'], 1)
        self.assertEqual(result['unit_price'], 5.99)
        self.assertEqual(result['total_price'], 5.99)

    def test_line_item_auto_correction(self):
        """Test that total_price is auto-corrected if wrong"""
        item = LineItem(
            name="Test Item",
            quantity=2,
            unit_price=10.00,
            total_price=15.00  # Wrong, should be 20.00
        )
        # Should auto-correct to 20.00
        self.assertEqual(item.total_price, Decimal("20.00"))


class TestReceiptData(unittest.TestCase):
    """Test ReceiptData Pydantic model"""

    def setUp(self):
        self.items = [
            LineItem(name="Item 1", quantity=1, unit_price=Decimal("10.00"), total_price=Decimal("10.00")),
            LineItem(name="Item 2", quantity=2, unit_price=Decimal("5.00"), total_price=Decimal("10.00"))
        ]

        self.receipt = ReceiptData(
            restaurant_name="Test Restaurant",
            date=datetime(2023, 10, 6),
            items=self.items,
            subtotal=Decimal("20.00"),
            tax=Decimal("2.00"),
            tip=Decimal("3.00"),
            total=Decimal("25.00"),
            confidence_score=0.95
        )

    def test_receipt_creation(self):
        self.assertEqual(self.receipt.restaurant_name, "Test Restaurant")
        self.assertEqual(len(self.receipt.items), 2)
        self.assertEqual(self.receipt.total, Decimal("25.00"))

    def test_receipt_to_dict(self):
        result = self.receipt.to_dict()

        self.assertEqual(result['restaurant_name'], "Test Restaurant")
        self.assertEqual(result['subtotal'], 20.00)
        self.assertEqual(result['tax'], 2.00)
        self.assertEqual(result['tip'], 3.00)
        self.assertEqual(result['total'], 25.00)
        self.assertEqual(len(result['items']), 2)

    def test_validation_valid(self):
        is_valid, errors = self.receipt.validate_totals()
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validation_invalid_subtotal(self):
        # Create receipt where items don't sum to subtotal
        receipt = ReceiptData(
            restaurant_name="Test",
            date=datetime.now(),
            items=self.items,
            subtotal=Decimal("50.00"),  # Wrong subtotal
            tax=Decimal("2.00"),
            tip=Decimal("3.00"),
            total=Decimal("55.00"),
            confidence_score=0.9
        )

        is_valid, errors = receipt.validate_totals()
        self.assertFalse(is_valid)
        self.assertTrue(any("Items sum" in e for e in errors))

    def test_validation_invalid_total(self):
        # Create receipt where subtotal + tax + tip != total
        receipt = ReceiptData(
            restaurant_name="Test",
            date=datetime.now(),
            items=self.items,
            subtotal=Decimal("20.00"),
            tax=Decimal("2.00"),
            tip=Decimal("3.00"),
            total=Decimal("30.00"),  # Wrong total
            confidence_score=0.9
        )

        is_valid, errors = receipt.validate_totals()
        self.assertFalse(is_valid)
        self.assertTrue(any("Calculated total" in e for e in errors))

    def test_validation_negative_values(self):
        # Negative tax should fail at Pydantic validation
        with self.assertRaises(Exception) as context:
            receipt = ReceiptData(
                restaurant_name="Test",
                date=datetime.now(),
                items=self.items,
                subtotal=Decimal("20.00"),
                tax=Decimal("-2.00"),  # Negative tax
                tip=Decimal("3.00"),
                total=Decimal("21.00"),
                confidence_score=0.9
            )

        # Should raise ValidationError from Pydantic
        self.assertIn("greater than or equal to 0", str(context.exception))

    def test_negative_tip_allowed(self):
        """Test that negative tip (discount) is allowed"""
        receipt = ReceiptData(
            restaurant_name="Test",
            date=datetime.now(),
            items=self.items,
            subtotal=Decimal("20.00"),
            tax=Decimal("2.00"),
            tip=Decimal("-3.00"),  # Negative tip (discount)
            total=Decimal("19.00"),
            confidence_score=0.9
        )

        is_valid, errors = receipt.validate_totals()
        self.assertTrue(is_valid)  # Should be valid with negative tip


class TestReceiptOCR(unittest.TestCase):
    """Test ReceiptOCR class"""

    @patch('lib.ocr.ocr_lib.genai.Client')
    def test_initialization(self, mock_genai_client):
        ocr = ReceiptOCR("test_key", model="gemini-3-flash-preview")
        mock_genai_client.assert_called_once_with(api_key="test_key")
        self.assertEqual(ocr.model, "gemini-3-flash-preview")
        self.assertEqual(ocr.thinking_level, "low")

    def test_pydantic_parsing(self):
        """Test that Pydantic properly parses receipt data"""
        data = {
            'restaurant_name': 'Test Restaurant',
            'date': '2023-10-06',
            'items': [
                {
                    'name': 'Item 1',
                    'quantity': 2,
                    'unit_price': 10.50,
                    'total_price': 21.00
                }
            ],
            'subtotal': 21.00,
            'tax': 2.00,
            'tip': 3.00,
            'total': 26.00,
            'confidence_score': 0.95
        }

        receipt = ReceiptData.model_validate(data)

        self.assertEqual(receipt.restaurant_name, 'Test Restaurant')
        self.assertEqual(receipt.date.strftime('%Y-%m-%d'), '2023-10-06')
        self.assertEqual(len(receipt.items), 1)
        self.assertEqual(receipt.items[0].name, 'Item 1')
        self.assertEqual(receipt.total, Decimal('26.00'))
        self.assertEqual(receipt.confidence_score, 0.95)

    @patch('lib.ocr.ocr_lib.genai.Client')
    def test_prepare_image_exif_rotation(self, mock_genai_client):
        """Test that _prepare_image applies EXIF rotation"""
        from PIL import Image
        from io import BytesIO

        # Create a simple test JPEG image
        img = Image.new('RGB', (100, 100), color='red')
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        test_bytes = buffer.getvalue()

        ocr = ReceiptOCR("test_key", )
        result_bytes, result_mime = ocr._prepare_image(test_bytes, "image/jpeg")

        # Should return bytes and preserve mime type
        self.assertIsInstance(result_bytes, bytes)
        self.assertEqual(result_mime, "image/jpeg")
        self.assertGreater(len(result_bytes), 0)

    @patch('lib.ocr.ocr_lib.Image.open')
    def test_process_image_file_not_found(self, mock_open):
        ocr = ReceiptOCR("test_key", )

        with self.assertRaises(FileNotFoundError):
            ocr.process_image("nonexistent.jpg")


class TestIntegration(unittest.TestCase):
    """Test full integration flow"""

    @patch('lib.ocr.ocr_lib.ReceiptOCR._ocr_api_call')
    @patch('lib.ocr.ocr_lib.genai.Client')
    def test_process_image_success(self, mock_genai_client, mock_ocr_api_call):
        # Mock OCR API call to return JSON string directly
        mock_ocr_api_call.return_value = json.dumps({
            'restaurant_name': 'Test Restaurant',
            'date': '2023-10-06',
            'items': [
                {
                    'name': 'Burger',
                    'quantity': 1,
                    'unit_price': 12.00,
                    'total_price': 12.00
                }
            ],
            'subtotal': 12.00,
            'tax': 1.00,
            'tip': 2.00,
            'total': 15.00,
            'confidence_score': 0.95,
            'notes': None
        })

        # Test - use bytes to avoid file system checks
        ocr = ReceiptOCR("test_key", model="gemini-3-flash-preview", )

        # Create a minimal valid JPEG for PIL to open
        from PIL import Image
        from io import BytesIO
        img = Image.new('RGB', (10, 10), color='white')
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        dummy_image = buffer.getvalue()

        receipt = ocr.process_image(dummy_image)

        # Verify result
        self.assertEqual(receipt.restaurant_name, 'Test Restaurant')
        self.assertEqual(receipt.total, Decimal('15.00'))
        self.assertEqual(len(receipt.items), 1)

        # Verify OCR API method was called
        mock_ocr_api_call.assert_called_once()

    @patch('lib.ocr.ocr_lib.genai.Client')
    def test_process_image_api_error(self, mock_genai_client):
        # Setup mocks
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client

        # Mock API error
        mock_client.models.generate_content.side_effect = Exception("API Error")

        # Test
        ocr = ReceiptOCR("test_key", )

        # Create a minimal valid JPEG for PIL to open
        from PIL import Image
        from io import BytesIO
        img = Image.new('RGB', (10, 10), color='white')
        buffer = BytesIO()
        img.save(buffer, format='JPEG')

        with self.assertRaises(ValueError) as context:
            ocr.process_image(buffer.getvalue())

        self.assertIn("Failed to process image with Gemini", str(context.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)
