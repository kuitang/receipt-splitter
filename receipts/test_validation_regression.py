"""
Regression tests for validation bugs:
1. Decimal(str(Fraction)) crashes for fractional item validation
2. utils.js loaded twice causes SyntaxError (template test)
"""
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal

from .models import Receipt, LineItem
from .validation import validate_receipt_balance


class FractionalItemValidationTests(TestCase):
    """Decimal(str(Fraction(1,2))) crashes. Validation must handle fractional items."""

    def test_validate_fractional_item_does_not_crash(self):
        """Item with quantity_numerator=1, quantity_denominator=2 should not crash."""
        receipt_data = {
            'subtotal': '5.00',
            'tax': '0.50',
            'tip': '1.00',
            'total': '6.50',
            'items': [
                {
                    'name': 'Half Pizza',
                    'quantity_numerator': 1,
                    'quantity_denominator': 2,
                    'unit_price': '10.00',
                    'total_price': '5.00',
                }
            ],
        }
        is_valid, errors = validate_receipt_balance(receipt_data)
        self.assertTrue(is_valid)

    def test_validate_fractional_item_checks_math(self):
        """Fractional item: 1/2 * $10.00 should equal $5.00."""
        receipt_data = {
            'subtotal': '5.00',
            'tax': '0.00',
            'tip': '0.00',
            'total': '5.00',
            'items': [
                {
                    'name': 'Half Pizza',
                    'quantity_numerator': 1,
                    'quantity_denominator': 2,
                    'unit_price': '10.00',
                    'total_price': '5.00',
                }
            ],
        }
        is_valid, errors = validate_receipt_balance(receipt_data)
        self.assertTrue(is_valid)

    def test_validate_fractional_item_wrong_total(self):
        """Fractional item with wrong total should fail validation."""
        receipt_data = {
            'subtotal': '7.00',
            'tax': '0.00',
            'tip': '0.00',
            'total': '7.00',
            'items': [
                {
                    'name': 'Half Pizza',
                    'quantity_numerator': 1,
                    'quantity_denominator': 2,
                    'unit_price': '10.00',
                    'total_price': '7.00',  # Wrong: should be 5.00
                }
            ],
        }
        is_valid, errors = validate_receipt_balance(receipt_data)
        self.assertFalse(is_valid)
        self.assertIn('items', errors)

    def test_validate_third_fraction(self):
        """1/3 * $30.00 should equal $10.00."""
        receipt_data = {
            'subtotal': '10.00',
            'tax': '0.00',
            'tip': '0.00',
            'total': '10.00',
            'items': [
                {
                    'name': 'Third of Platter',
                    'quantity_numerator': 1,
                    'quantity_denominator': 3,
                    'unit_price': '30.00',
                    'total_price': '10.00',
                }
            ],
        }
        is_valid, errors = validate_receipt_balance(receipt_data)
        self.assertTrue(is_valid)

    def test_validate_integer_quantity_still_works(self):
        """Integer quantity (denominator=1) should still validate correctly."""
        receipt_data = {
            'subtotal': '20.00',
            'tax': '0.00',
            'tip': '0.00',
            'total': '20.00',
            'items': [
                {
                    'name': 'Burger',
                    'quantity_numerator': 2,
                    'quantity_denominator': 1,
                    'unit_price': '10.00',
                    'total_price': '20.00',
                }
            ],
        }
        is_valid, errors = validate_receipt_balance(receipt_data)
        self.assertTrue(is_valid)


class DoubleScriptLoadTest(TestCase):
    """utils.js must only be loaded once per page. base.html loads it globally,
    so child templates must NOT load it again in extra_scripts."""

    def test_edit_page_no_duplicate_utils(self):
        """edit_async.html extra_scripts should not include utils.js."""
        from django.template.loader import get_template
        template = get_template('receipts/edit_async.html')
        source = template.template.source
        # Count occurrences of utils.js in the template source
        import re
        utils_loads = re.findall(r"static\s+'js/utils\.js'", source)
        self.assertEqual(len(utils_loads), 0,
                         "edit_async.html should not load utils.js (base.html already loads it)")

    def test_view_page_no_duplicate_utils(self):
        """view.html extra_scripts should not include utils.js."""
        from django.template.loader import get_template
        template = get_template('receipts/view.html')
        source = template.template.source
        import re
        utils_loads = re.findall(r"static\s+'js/utils\.js'", source)
        self.assertEqual(len(utils_loads), 0,
                         "view.html should not load utils.js (base.html already loads it)")
