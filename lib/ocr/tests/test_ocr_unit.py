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
    
    @patch('lib.ocr.ocr_lib.OpenAI')
    def test_initialization(self, mock_openai):
        ocr = ReceiptOCR("test_key", model="gpt-4o", seed_test_cache=False)
        mock_openai.assert_called_once_with(api_key="test_key")
        self.assertEqual(ocr.model, "gpt-4o")
    
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
    
    @patch('PIL.ImageOps.exif_transpose')
    @patch('lib.ocr.ocr_lib.Image.open')
    def test_preprocess_image(self, mock_open, mock_exif):
        mock_image = MagicMock()
        mock_image.mode = 'RGBA'
        mock_image.size = (3000, 2000)
        
        # Mock convert to return RGB image
        mock_rgb = MagicMock()
        mock_rgb.mode = 'RGB'
        mock_rgb.size = (3000, 2000)
        mock_rgb.thumbnail = MagicMock()
        mock_image.convert.return_value = mock_rgb
        
        # Mock exif_transpose to return the converted image with size preserved
        mock_exif.return_value = mock_rgb
        
        ocr = ReceiptOCR("test_key", seed_test_cache=False)
        result = ocr._preprocess_image(mock_image)
        
        # Should convert to RGB
        mock_image.convert.assert_called_once_with('RGB')
        # Should resize if too large
        mock_rgb.thumbnail.assert_called_once()
    
    @patch('lib.ocr.ocr_lib.Image.open')
    @patch.object(ReceiptOCR, '_image_to_base64')
    def test_process_image_file_not_found(self, mock_base64, mock_open):
        ocr = ReceiptOCR("test_key", seed_test_cache=False)
        
        with self.assertRaises(FileNotFoundError):
            ocr.process_image("nonexistent.jpg")


class TestIntegration(unittest.TestCase):
    """Test full integration flow"""
    
    @patch('lib.ocr.ocr_lib.ReceiptOCR._ocr_api_call')
    @patch('PIL.ImageOps.exif_transpose')
    @patch('lib.ocr.ocr_lib.Image.open')
    def test_process_image_success(self, mock_image_open, mock_exif, mock_ocr_api_call):
        # Mock image
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.size = (1000, 1000)
        mock_image_open.return_value = mock_image
        
        # Mock exif_transpose to return the same image with size preserved
        mock_exif.return_value = mock_image
        
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
            'confidence_score': 0.95
        })
        
        # Test - use bytes to avoid file system checks, specify model explicitly
        ocr = ReceiptOCR("test_key", model="gpt-4o", seed_test_cache=False)
        
        # Process image from bytes
        dummy_image = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        receipt = ocr.process_image(dummy_image)
        
        # Verify result
        self.assertEqual(receipt.restaurant_name, 'Test Restaurant')
        self.assertEqual(receipt.total, Decimal('15.00'))
        self.assertEqual(len(receipt.items), 1)
        
        # Verify OCR API method was called
        mock_ocr_api_call.assert_called_once()
    
    @patch('lib.ocr.ocr_lib.OpenAI')
    @patch('PIL.ImageOps.exif_transpose')
    @patch('lib.ocr.ocr_lib.Image.open')
    def test_process_image_api_error(self, mock_image_open, mock_exif, mock_openai_class):
        # Setup mocks
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock image
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.size = (100, 100)
        mock_image_open.return_value = mock_image
        
        # Mock exif_transpose to return the same image with size preserved
        mock_exif.return_value = mock_image
        
        # Mock API error
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        # Test
        ocr = ReceiptOCR("test_key", seed_test_cache=False)
        
        with self.assertRaises(ValueError) as context:
            ocr.process_image(b"dummy")
        
        self.assertIn("Failed to process image with OpenAI", str(context.exception))


class TestIMG6839Cache(unittest.TestCase):
    """Test IMG_6839.HEIC caching functionality"""
    
    @patch('lib.ocr.ocr_lib.OpenAI')
    def test_img_6839_cache_hit_no_api_call(self, mock_openai_class):
        """Test that processing IMG_6839.HEIC uses cache and never calls OpenAI API"""
        
        # Setup mock to track API calls
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # This should NEVER be called for IMG_6839.HEIC
        mock_client.chat.completions.create.side_effect = Exception("API should not be called for IMG_6839.HEIC!")
        
        # Initialize OCR with cache seeding
        ocr = ReceiptOCR("test_key", cache_size=128, seed_test_cache=True)
        
        # Path to the test image
        test_image_path = Path(__file__).parent.parent / "test_data" / "IMG_6839.HEIC"
        if not test_image_path.exists():
            self.skipTest(f"Test image not found: {test_image_path}")
        
        # Process the image - this should use hardcoded results, not API
        try:
            result = ocr.process_image(test_image_path)
            
            # Verify we got valid receipt data
            self.assertIsInstance(result, ReceiptData)
            self.assertEqual(result.restaurant_name, "The Gin Mill (NY)")
            self.assertEqual(len(result.items), 7)
            self.assertEqual(float(result.total), 64.0)
            
            # Verify no API calls were made
            mock_client.chat.completions.create.assert_not_called()
            
        except Exception as e:
            if "API should not be called" in str(e):
                self.fail("API was called when it should have used hardcoded results")
            else:
                raise
    
    @patch('lib.ocr.ocr_lib.OpenAI')
    def test_cache_seeding_disabled(self, mock_openai_class):
        """Test that cache seeding can be disabled"""
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Create OCR instance with cache seeding disabled
        ocr = ReceiptOCR("test_key", cache_size=128, seed_test_cache=False)
        
        # IMG_6839 hash should not be computed
        self.assertIsNone(ocr._img_6839_hash)


if __name__ == '__main__':
    unittest.main(verbosity=2)