from django.test import TestCase
from unittest.mock import patch, MagicMock
from decimal import Decimal
from django.utils import timezone

from receipts.models import Receipt
from receipts.async_processor import _process_receipt_worker

class AsyncProcessorTests(TestCase):
    def setUp(self):
        self.receipt = Receipt.objects.create(
            uploader_name="Test User",
            restaurant_name="Processing...",
            date=timezone.now(),
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            tip=Decimal("0"),
            total=Decimal("0"),
            processing_status='pending'
        )

    @patch('receipts.async_processor.process_receipt_with_ocr')
    def test_process_receipt_worker_exception(self, mock_process_receipt):
        """Test that an exception in the worker is logged and the receipt is updated."""
        mock_process_receipt.side_effect = Exception("OCR failed")

        with self.assertLogs('receipts.async_processor', level='ERROR') as cm:
            _process_receipt_worker(self.receipt.id, b"image_content")
            self.assertIn("Error processing receipt", cm.output[0])

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.processing_status, 'failed')
        self.assertEqual(self.receipt.processing_error, "An unexpected error occurred during processing.")
