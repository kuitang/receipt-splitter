"""
Tests for async_processor.py — specifically that OCR results
create LineItems using quantity_numerator (not the removed quantity field)
and that fractional Decimal conversions don't crash.
"""
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from fractions import Fraction
from unittest.mock import patch

from .models import Receipt, LineItem, Claim
from .async_processor import _process_receipt_worker


class AsyncProcessorLineItemCreationTests(TestCase):
    """Regression: _process_receipt_worker must use quantity_numerator, not quantity."""

    def setUp(self):
        self.receipt = Receipt.objects.create(
            uploader_name="Test",
            restaurant_name="Processing...",
            date=timezone.now(),
            subtotal=Decimal('0'),
            tax=Decimal('0'),
            tip=Decimal('0'),
            total=Decimal('0'),
            processing_status='pending',
        )
        # Placeholder item (like create_placeholder_receipt makes)
        LineItem.objects.create(
            receipt=self.receipt,
            name="Analyzing...",
            unit_price=Decimal('0'),
            total_price=Decimal('0'),
        )

    @patch('receipts.async_processor.process_receipt_with_ocr')
    def test_ocr_creates_line_items_with_quantity_numerator(self, mock_ocr):
        """OCR results should set quantity_numerator on LineItems."""
        mock_ocr.return_value = {
            'restaurant_name': 'Test Diner',
            'date': timezone.now(),
            'subtotal': 20.0,
            'tax': 2.0,
            'tip': 3.0,
            'total': 25.0,
            'items': [
                {'name': 'Burger', 'quantity': 2, 'unit_price': 5.0, 'total_price': 10.0},
                {'name': 'Fries', 'quantity': 1, 'unit_price': 10.0, 'total_price': 10.0},
            ],
        }

        _process_receipt_worker(self.receipt.id, b'fake_image', 'JPEG')

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.processing_status, 'completed')
        self.assertEqual(self.receipt.restaurant_name, 'Test Diner')

        items = list(self.receipt.items.order_by('name'))
        self.assertEqual(len(items), 2)

        burger = items[0]
        self.assertEqual(burger.name, 'Burger')
        self.assertEqual(burger.quantity_numerator, 2)
        self.assertEqual(burger.quantity_denominator, 1)

        fries = items[1]
        self.assertEqual(fries.name, 'Fries')
        self.assertEqual(fries.quantity_numerator, 1)

    @patch('receipts.async_processor.process_receipt_with_ocr')
    def test_ocr_failure_sets_failed_status(self, mock_ocr):
        """If OCR raises, receipt status should be 'failed'."""
        mock_ocr.side_effect = RuntimeError("OCR exploded")

        _process_receipt_worker(self.receipt.id, b'fake_image', 'JPEG')

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.processing_status, 'failed')


class FractionalDecimalConversionTests(TestCase):
    """Regression: Decimal(str(Fraction(1,2))) crashes. Ensure share calculations work."""

    def setUp(self):
        self.receipt = Receipt.objects.create(
            uploader_name="Test",
            restaurant_name="Fraction Diner",
            date=timezone.now(),
            subtotal=Decimal('20.00'),
            tax=Decimal('2.00'),
            tip=Decimal('3.00'),
            total=Decimal('25.00'),
            is_finalized=True,
        )
        # Item split into 2 parts
        self.item = LineItem.objects.create(
            receipt=self.receipt,
            name="Pizza",
            quantity_numerator=2,
            quantity_denominator=1,
            unit_price=Decimal('10.00'),
            total_price=Decimal('20.00'),
        )
        self.item.calculate_prorations()
        self.item.save()

    def test_claim_get_share_amount_fractional(self):
        """Claim.get_share_amount() must not crash for fractional shares."""
        claim = Claim.objects.create(
            line_item=self.item,
            claimer_name="Alice",
            quantity_numerator=1,
            session_id="test-session",
        )
        # 1/2 of item total_share — should not raise
        share = claim.get_share_amount()
        self.assertIsInstance(share, Decimal)
        self.assertGreater(share, Decimal('0'))

    def test_view_receipt_my_total_fractional(self):
        """The view_receipt view must compute my_total without Decimal(str(Fraction)) crash."""
        claim = Claim.objects.create(
            line_item=self.item,
            claimer_name="Bob",
            quantity_numerator=1,
            session_id="test-session",
            is_finalized=True,
        )

        client = self.client
        # Set viewer name via session manager namespace
        session = client.session
        session['receipts'] = {
            str(self.receipt.id): {'viewer_name': 'Bob'}
        }
        session.save()

        response = client.get(f'/r/{self.receipt.slug}/')
        self.assertEqual(response.status_code, 200)
        # my_total should be computed without error
        self.assertIn('my_total', response.context)
        self.assertGreater(response.context['my_total'], Decimal('0'))
