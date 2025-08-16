#!/usr/bin/env python3
"""
Unit tests for OCR total correction algorithm
Tests the invariant: line items MUST add up to the Total
"""

import unittest
from decimal import Decimal
from datetime import datetime
from ocr_lib import ReceiptData, LineItem


class TestTotalCorrection(unittest.TestCase):
    """Test the total correction algorithm"""
    
    def create_receipt(self, subtotal, tax, tip, total, items=None):
        """Helper to create a test receipt"""
        if items is None:
            # Create items that sum to subtotal
            items = [
                LineItem("Item 1", 1, Decimal(str(subtotal)), Decimal(str(subtotal)))
            ]
        
        return ReceiptData(
            restaurant_name="Test Restaurant",
            date=datetime.now(),
            items=items,
            subtotal=Decimal(str(subtotal)),
            tax=Decimal(str(tax)),
            tip=Decimal(str(tip)),
            total=Decimal(str(total)),
            confidence_score=0.95
        )
    
    def test_gin_mill_case(self):
        """Test the actual Gin Mill receipt case: zero tax/tip with discrepancy"""
        # Create receipt matching the real Gin Mill data
        items = [
            LineItem("WELL TEQUILA", 1, Decimal("5.00"), Decimal("5.00")),
            LineItem("AMARETTO", 1, Decimal("17.00"), Decimal("17.00")),
            LineItem("PALOMA", 1, Decimal("8.50"), Decimal("8.50")),
            LineItem("HAPPY HOUR BEER", 1, Decimal("5.00"), Decimal("5.00")),
            LineItem("WELL GIN", 1, Decimal("5.00"), Decimal("5.00")),
            LineItem("CONEY ISLAND DRAFT", 1, Decimal("8.00"), Decimal("8.00")),
            LineItem("MEZCAL ME GINGER", 1, Decimal("12.00"), Decimal("12.00"))
        ]
        
        receipt = ReceiptData(
            restaurant_name="The Gin Mill (NY)",
            date=datetime.now(),
            items=items,
            subtotal=Decimal("60.50"),
            tax=Decimal("0"),
            tip=Decimal("0"),
            total=Decimal("64.00"),
            confidence_score=0.95
        )
        
        # Validate shows error
        is_valid, errors = receipt.validate()
        self.assertFalse(is_valid)
        self.assertTrue(any("doesn't match receipt total" in e for e in errors))
        
        # Apply correction
        corrections = receipt.correct_totals()
        
        # Check corrections were applied
        self.assertTrue(corrections['applied'])
        self.assertEqual(corrections['reason'], 'Discrepancy treated as tip/service charge')
        self.assertEqual(corrections['discrepancy'], 3.5)
        
        # Check corrected values
        self.assertEqual(receipt.subtotal, Decimal("60.50"))
        self.assertEqual(receipt.tax, Decimal("0"))
        self.assertEqual(receipt.tip, Decimal("3.50"))  # Discrepancy moved to tip
        self.assertEqual(receipt.total, Decimal("64.00"))
        
        # Validate after correction - should pass
        is_valid_after, errors_after = receipt.validate()
        self.assertTrue(is_valid_after)
        self.assertEqual(len(errors_after), 0)
    
    def test_no_correction_needed(self):
        """Test when totals already match"""
        receipt = self.create_receipt(
            subtotal=50.00,
            tax=5.00,
            tip=10.00,
            total=65.00
        )
        
        # Already valid
        is_valid, _ = receipt.validate()
        self.assertTrue(is_valid)
        
        # Apply correction
        corrections = receipt.correct_totals()
        
        # No correction needed
        self.assertFalse(corrections['applied'])
        self.assertEqual(corrections['reason'], 'Totals already match')
        
        # Values unchanged
        self.assertEqual(receipt.subtotal, Decimal("50.00"))
        self.assertEqual(receipt.tax, Decimal("5.00"))
        self.assertEqual(receipt.tip, Decimal("10.00"))
    
    def test_proportional_adjustment(self):
        """Test proportional adjustment when tax and tip exist"""
        receipt = self.create_receipt(
            subtotal=100.00,
            tax=8.00,
            tip=15.00,
            total=130.00  # Should be 123, discrepancy of 7
        )
        
        # Apply correction
        corrections = receipt.correct_totals()
        
        self.assertTrue(corrections['applied'])
        self.assertEqual(corrections['reason'], 'Proportionally adjusted tax and tip')
        
        # Tax and tip should be proportionally increased
        # Original ratio: tax=8/(8+15)=0.348, tip=15/(8+15)=0.652
        # Discrepancy of 7: tax gets ~2.43, tip gets ~4.57
        self.assertAlmostEqual(float(receipt.tax), 10.43, places=1)
        self.assertAlmostEqual(float(receipt.tip), 19.57, places=1)
        
        # Total should match
        self.assertEqual(receipt.subtotal + receipt.tax + receipt.tip, receipt.total)
    
    def test_negative_discrepancy_discount(self):
        """Test negative discrepancy treated as discount"""
        receipt = self.create_receipt(
            subtotal=50.00,
            tax=0,
            tip=0,
            total=45.00  # $5 discount
        )
        
        # Apply correction
        corrections = receipt.correct_totals()
        
        self.assertTrue(corrections['applied'])
        self.assertEqual(corrections['reason'], 'Negative discrepancy treated as discount')
        
        # Negative tip represents discount
        self.assertEqual(receipt.tip, Decimal("-5.00"))
        self.assertEqual(receipt.subtotal + receipt.tax + receipt.tip, receipt.total)
    
    def test_subtotal_items_mismatch(self):
        """Test when subtotal doesn't match items sum"""
        items = [
            LineItem("Item 1", 2, Decimal("10.00"), Decimal("20.00")),
            LineItem("Item 2", 1, Decimal("15.00"), Decimal("15.00"))
        ]
        
        receipt = ReceiptData(
            restaurant_name="Test",
            date=datetime.now(),
            items=items,
            subtotal=Decimal("40.00"),  # Wrong! Items sum to 35
            tax=Decimal("3.00"),
            tip=Decimal("5.00"),
            total=Decimal("43.00"),  # Should be 35+3+5=43
            confidence_score=0.9
        )
        
        # Apply correction
        corrections = receipt.correct_totals()
        
        # Subtotal should be corrected to match items
        self.assertEqual(receipt.subtotal, Decimal("35.00"))
        self.assertEqual(receipt.subtotal + receipt.tax + receipt.tip, receipt.total)
    
    def test_edge_case_zero_total(self):
        """Test edge case with zero total"""
        receipt = self.create_receipt(
            subtotal=0,
            tax=0,
            tip=0,
            total=0
        )
        
        corrections = receipt.correct_totals()
        self.assertFalse(corrections['applied'])
        self.assertEqual(corrections['reason'], 'Totals already match')
    
    def test_large_discrepancy(self):
        """Test with large discrepancy"""
        receipt = self.create_receipt(
            subtotal=100.00,
            tax=0,
            tip=0,
            total=200.00  # $100 discrepancy
        )
        
        corrections = receipt.correct_totals()
        
        self.assertTrue(corrections['applied'])
        # Large discrepancy treated as tip/service charge
        self.assertEqual(receipt.tip, Decimal("100.00"))
        self.assertEqual(receipt.subtotal + receipt.tax + receipt.tip, receipt.total)
    
    def test_tax_only_adjustment(self):
        """Test adjustment when only tax exists (no tip)"""
        receipt = self.create_receipt(
            subtotal=50.00,
            tax=5.00,
            tip=0,
            total=60.00  # Should be 55, discrepancy of 5
        )
        
        corrections = receipt.correct_totals()
        
        self.assertTrue(corrections['applied'])
        # All discrepancy goes to tax since tip is 0
        self.assertEqual(receipt.tax, Decimal("10.00"))
        self.assertEqual(receipt.tip, Decimal("0"))
        self.assertEqual(receipt.subtotal + receipt.tax + receipt.tip, receipt.total)
    
    def test_negative_tax_transfer(self):
        """Test when adjustment would make tax negative"""
        receipt = self.create_receipt(
            subtotal=100.00,
            tax=2.00,
            tip=10.00,
            total=100.00  # Should be 112, discrepancy of -12
        )
        
        corrections = receipt.correct_totals()
        
        self.assertTrue(corrections['applied'])
        # Tax and tip should be reduced, but not below 0
        self.assertGreaterEqual(receipt.tax, Decimal("0"))
        self.assertGreaterEqual(receipt.tip, Decimal("0"))
        self.assertEqual(receipt.subtotal + receipt.tax + receipt.tip, receipt.total)


class TestOCRInterfaceCorrection(unittest.TestCase):
    """Test OCR interface with correction"""
    
    def test_receipt_data_to_dict_after_correction(self):
        """Test that to_dict works after correction"""
        receipt = ReceiptData(
            restaurant_name="Test",
            date=datetime.now(),
            items=[LineItem("Item", 1, Decimal("10"), Decimal("10"))],
            subtotal=Decimal("10"),
            tax=Decimal("0"),
            tip=Decimal("0"),
            total=Decimal("12"),  # $2 discrepancy
            confidence_score=0.9
        )
        
        # Apply correction
        corrections = receipt.correct_totals()
        self.assertTrue(corrections['applied'])
        
        # Convert to dict
        data = receipt.to_dict()
        
        # Check corrected values in dict
        self.assertEqual(data['subtotal'], 10.0)
        self.assertEqual(data['tax'], 0.0)
        self.assertEqual(data['tip'], 2.0)  # Discrepancy
        self.assertEqual(data['total'], 12.0)
        
        # Verify total invariant
        self.assertEqual(
            data['subtotal'] + data['tax'] + data['tip'],
            data['total']
        )


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)