#!/usr/bin/env python3
"""
Unit tests for OCR library interface
Tests the API without making actual OpenAI calls
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import json

from ocr_lib import ReceiptOCR, ReceiptData, LineItem


class TestLineItem(unittest.TestCase):
    """Test LineItem dataclass"""
    
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


class TestReceiptData(unittest.TestCase):
    """Test ReceiptData dataclass"""
    
    def setUp(self):
        self.items = [
            LineItem("Item 1", 1, Decimal("10.00"), Decimal("10.00")),
            LineItem("Item 2", 2, Decimal("5.00"), Decimal("10.00"))
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
        is_valid, errors = self.receipt.validate()
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
        
        is_valid, errors = receipt.validate()
        self.assertFalse(is_valid)
        self.assertTrue(any("doesn't match subtotal" in e for e in errors))
    
    def test_validation_invalid_total(self):
        # Create receipt where total doesn't match calculation
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
        
        is_valid, errors = receipt.validate()
        self.assertFalse(is_valid)
        self.assertTrue(any("doesn't match receipt total" in e for e in errors))
    
    def test_validation_negative_values(self):
        receipt = ReceiptData(
            restaurant_name="Test",
            date=datetime.now(),
            items=[],
            subtotal=Decimal("-10.00"),
            tax=Decimal("1.00"),
            tip=Decimal("2.00"),
            total=Decimal("-7.00"),
            confidence_score=0.9
        )
        
        is_valid, errors = receipt.validate()
        self.assertFalse(is_valid)
        self.assertTrue(any("Negative values" in e for e in errors))


class TestReceiptOCR(unittest.TestCase):
    """Test ReceiptOCR class"""
    
    def setUp(self):
        self.ocr = ReceiptOCR("test_api_key")
    
    @patch('ocr_lib.OpenAI')
    def test_initialization(self, mock_openai):
        ocr = ReceiptOCR("test_key", model="gpt-4o")
        mock_openai.assert_called_once_with(api_key="test_key")
        self.assertEqual(ocr.model, "gpt-4o")
    
    def test_parse_response_valid_json(self):
        response = '{"restaurant_name": "Test", "total": 25.00}'
        result = self.ocr._parse_response(response)
        self.assertEqual(result['restaurant_name'], "Test")
        self.assertEqual(result['total'], 25.00)
    
    def test_parse_response_with_markdown(self):
        response = '```json\n{"restaurant_name": "Test", "total": 25.00}\n```'
        result = self.ocr._parse_response(response)
        self.assertEqual(result['restaurant_name'], "Test")
    
    def test_parse_response_invalid_json(self):
        response = 'This is not JSON'
        with self.assertRaises(ValueError) as context:
            self.ocr._parse_response(response)
        self.assertIn("No JSON found", str(context.exception))
    
    def test_data_to_receipt(self):
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
        
        receipt = self.ocr._data_to_receipt(data, "raw text")
        
        self.assertEqual(receipt.restaurant_name, 'Test Restaurant')
        self.assertEqual(receipt.date.strftime('%Y-%m-%d'), '2023-10-06')
        self.assertEqual(len(receipt.items), 1)
        self.assertEqual(receipt.items[0].name, 'Item 1')
        self.assertEqual(receipt.total, Decimal('26.00'))
        self.assertEqual(receipt.confidence_score, 0.95)
    
    def test_data_to_receipt_missing_date(self):
        data = {
            'restaurant_name': 'Test',
            'items': [],
            'subtotal': 0,
            'tax': 0,
            'tip': 0,
            'total': 0
        }
        
        receipt = self.ocr._data_to_receipt(data, "")
        # Should use today's date
        self.assertEqual(receipt.date.date(), datetime.now().date())
    
    @patch('ocr_lib.Image.open')
    @patch.object(ReceiptOCR, '_image_to_base64')
    def test_process_image_file_not_found(self, mock_base64, mock_open):
        with self.assertRaises(FileNotFoundError):
            self.ocr.process_image("nonexistent.jpg")
    
    @patch('ocr_lib.Image.open')
    def test_preprocess_image(self, mock_open):
        # Create a mock image with proper size property
        mock_image = MagicMock()
        mock_image.mode = 'RGBA'
        mock_image.size = MagicMock(return_value=(3000, 4000))
        mock_image.size.__iter__ = MagicMock(return_value=iter([3000, 4000]))
        mock_image.convert.return_value = mock_image
        mock_image.thumbnail = MagicMock()
        
        result = self.ocr._preprocess_image(mock_image)
        
        # Should convert to RGB
        mock_image.convert.assert_called_once_with('RGB')
        # Should resize large image
        mock_image.thumbnail.assert_called_once()


class TestIntegration(unittest.TestCase):
    """Test integration scenarios"""
    
    @patch('ocr_lib.OpenAI')
    @patch('ocr_lib.Image.open')
    def test_process_image_success(self, mock_image_open, mock_openai_class):
        # Setup mocks
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock image with proper size attribute
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.size = [1000, 1000]  # Use list for proper iteration
        mock_image_open.return_value = mock_image
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
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
            'confidence_score': 0.95
        })
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test
        ocr = ReceiptOCR("test_key")
        
        # Create a temporary test file
        test_file = Path("test_receipt.jpg")
        test_file.write_text("dummy")
        
        try:
            receipt = ocr.process_image(test_file)
            
            # Verify result
            self.assertEqual(receipt.restaurant_name, 'Test Restaurant')
            self.assertEqual(receipt.total, Decimal('15.00'))
            self.assertEqual(len(receipt.items), 1)
            
            # Verify API was called
            mock_client.chat.completions.create.assert_called_once()
            
        finally:
            test_file.unlink()
    
    @patch('ocr_lib.OpenAI')
    @patch('ocr_lib.Image.open')
    def test_process_image_api_error(self, mock_image_open, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock valid image
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.size = [1000, 1000]
        mock_image_open.return_value = mock_image
        
        # Mock API error
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        ocr = ReceiptOCR("test_key")
        
        with self.assertRaises(ValueError) as context:
            ocr.process_image_bytes(b"dummy", "JPEG")
        
        self.assertIn("Failed to process image with OpenAI", str(context.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)