"""
Unit tests for OCR correction tracking (ReceiptOCRResult / ReceiptOCRLineItem).
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from receipts.models import Receipt, LineItem, ReceiptOCRResult, ReceiptOCRLineItem
from receipts.queries import receipt_state


def _make_receipt(**kwargs):
    defaults = dict(
        uploader_name='Alice',
        restaurant_name='Test Cafe',
        date=timezone.now(),
        subtotal=Decimal('10.000000'),
        tax=Decimal('1.000000'),
        tip=Decimal('0.000000'),
        total=Decimal('11.000000'),
        processing_status='completed',
    )
    defaults.update(kwargs)
    return Receipt.objects.create(**defaults)


def _make_line_item(receipt, name='Burger', price='10.000000', **kwargs):
    item = LineItem.objects.create(
        receipt=receipt,
        name=name,
        quantity_numerator=kwargs.get('quantity_numerator', 1),
        quantity_denominator=kwargs.get('quantity_denominator', 1),
        unit_price=Decimal(price),
        total_price=Decimal(price),
    )
    item.calculate_prorations()
    item.save()
    return item


def _make_ocr_result(receipt):
    """Create an OCR snapshot matching the current receipt state."""
    ocr = ReceiptOCRResult.objects.create(
        receipt=receipt,
        restaurant_name=receipt.restaurant_name,
        date=receipt.date,
        subtotal=receipt.subtotal,
        tax=receipt.tax,
        tip=receipt.tip,
        total=receipt.total,
    )
    for item in receipt.items.order_by('id'):
        ReceiptOCRLineItem.objects.create(
            ocr_result=ocr,
            name=item.name,
            quantity_numerator=item.quantity_numerator,
            quantity_denominator=item.quantity_denominator,
            unit_price=item.unit_price,
            total_price=item.total_price,
            prorated_tax=item.prorated_tax,
            prorated_tip=item.prorated_tip,
        )
    return ocr


class IsCorrectedTests(TestCase):
    """Tests for ReceiptOCRResult.is_corrected()."""

    def test_not_corrected_when_all_fields_match(self):
        receipt = _make_receipt()
        _make_line_item(receipt)
        ocr = _make_ocr_result(receipt)
        self.assertFalse(ocr.is_corrected())

    def test_corrected_when_restaurant_name_changed(self):
        receipt = _make_receipt()
        _make_line_item(receipt)
        ocr = _make_ocr_result(receipt)

        receipt.restaurant_name = 'Different Cafe'
        receipt.save()

        self.assertTrue(ocr.is_corrected())

    def test_corrected_when_item_price_changed(self):
        receipt = _make_receipt()
        item = _make_line_item(receipt, price='10.000000')
        ocr = _make_ocr_result(receipt)

        item.total_price = Decimal('15.000000')
        item.save()

        self.assertTrue(ocr.is_corrected())

    def test_corrected_when_item_count_increased(self):
        receipt = _make_receipt()
        _make_line_item(receipt)
        ocr = _make_ocr_result(receipt)

        _make_line_item(receipt, name='Fries', price='3.000000')

        self.assertTrue(ocr.is_corrected())

    def test_corrected_when_item_removed(self):
        receipt = _make_receipt()
        item = _make_line_item(receipt)
        _make_line_item(receipt, name='Fries', price='3.000000')
        ocr = _make_ocr_result(receipt)

        item.delete()

        self.assertTrue(ocr.is_corrected())

    def test_corrected_when_item_name_changed(self):
        receipt = _make_receipt()
        item = _make_line_item(receipt)
        ocr = _make_ocr_result(receipt)

        item.name = 'Veggie Burger'
        item.save()

        self.assertTrue(ocr.is_corrected())

    def test_corrected_when_subtotal_changed(self):
        receipt = _make_receipt()
        _make_line_item(receipt)
        ocr = _make_ocr_result(receipt)

        receipt.subtotal = Decimal('12.000000')
        receipt.save()

        self.assertTrue(ocr.is_corrected())

    def test_decimal_equality_without_tolerance(self):
        """Exact decimal comparison — no floating point tolerance."""
        receipt = _make_receipt(subtotal=Decimal('10.123456'))
        _make_line_item(receipt)
        ocr = _make_ocr_result(receipt)
        self.assertFalse(ocr.is_corrected())

        receipt.subtotal = Decimal('10.123457')
        receipt.save()
        self.assertTrue(ocr.is_corrected())


class OCRResultSavedOnSuccessTests(TestCase):
    """Tests that _process_receipt_worker saves ReceiptOCRResult on success."""

    @patch('receipts.async_processor.process_receipt_with_ocr')
    def test_ocr_result_created_on_success(self, mock_ocr):
        mock_ocr.return_value = {
            'restaurant_name': 'Test Diner',
            'date': timezone.now(),
            'subtotal': 10.0,
            'tax': 1.0,
            'tip': 0.0,
            'total': 11.0,
            'items': [
                {'name': 'Burger', 'quantity': 1,
                 'unit_price': 10.0, 'total_price': 10.0},
            ],
        }

        receipt = _make_receipt(processing_status='pending')
        # Add placeholder item (as create_placeholder_receipt does)
        LineItem.objects.create(
            receipt=receipt,
            name='Analyzing...',
            unit_price=Decimal('0'),
            total_price=Decimal('0'),
        )

        from receipts.async_processor import _process_receipt_worker
        _process_receipt_worker(str(receipt.id), b'fakeimage', 'JPEG')

        self.assertTrue(
            ReceiptOCRResult.objects.filter(receipt=receipt).exists()
        )
        ocr = ReceiptOCRResult.objects.get(receipt=receipt)
        self.assertEqual(ocr.restaurant_name, 'Test Diner')
        self.assertEqual(ocr.ocr_items.count(), 1)
        self.assertEqual(ocr.ocr_items.first().name, 'Burger')

    @patch('receipts.async_processor.process_receipt_with_ocr')
    def test_ocr_result_not_created_on_failure(self, mock_ocr):
        mock_ocr.side_effect = Exception('OCR failed')

        receipt = _make_receipt(processing_status='pending')
        LineItem.objects.create(
            receipt=receipt,
            name='Analyzing...',
            unit_price=Decimal('0'),
            total_price=Decimal('0'),
        )

        from receipts.async_processor import _process_receipt_worker
        _process_receipt_worker(str(receipt.id), b'fakeimage', 'JPEG')

        self.assertFalse(
            ReceiptOCRResult.objects.filter(receipt=receipt).exists()
        )
        receipt.refresh_from_db()
        self.assertEqual(receipt.processing_status, 'failed')


class ReceiptStateTests(TestCase):
    """Tests for queries.receipt_state()."""

    def test_state_for_unfinalized_receipt_without_ocr(self):
        receipt = _make_receipt(processing_status='pending')
        state = receipt_state(receipt)
        self.assertFalse(state['finalized'])
        self.assertTrue(state['abandoned'])
        self.assertFalse(state['has_ocr'])
        self.assertFalse(state['corrected'])

    def test_state_for_finalized_uncorrected_receipt(self):
        receipt = _make_receipt()
        _make_line_item(receipt)
        _make_ocr_result(receipt)

        receipt.is_finalized = True
        receipt.save()

        state = receipt_state(receipt)
        self.assertTrue(state['finalized'])
        self.assertFalse(state['abandoned'])
        self.assertTrue(state['has_ocr'])
        self.assertFalse(state['corrected'])

    def test_state_corrected_after_edit(self):
        receipt = _make_receipt()
        _make_line_item(receipt)
        _make_ocr_result(receipt)

        receipt.restaurant_name = 'Edited Name'
        receipt.save()

        state = receipt_state(receipt)
        self.assertTrue(state['corrected'])

    def test_fully_claimed_when_all_items_claimed(self):
        from receipts.models import Claim
        receipt = _make_receipt()
        receipt.is_finalized = True
        receipt.save()
        item = _make_line_item(receipt)

        Claim.objects.create(
            line_item=item,
            claimer_name='Bob',
            quantity_numerator=item.quantity_numerator,
            session_id='sess1',
        )

        state = receipt_state(receipt)
        self.assertTrue(state['fully_claimed'])

    def test_not_fully_claimed_when_items_unclaimed(self):
        receipt = _make_receipt()
        _make_line_item(receipt)

        state = receipt_state(receipt)
        self.assertFalse(state['fully_claimed'])
