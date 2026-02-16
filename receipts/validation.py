"""
Receipt validation utilities

Validates that receipt totals balance correctly while allowing for discounts.
Tax and tip can be negative to represent discounts or corrections, as per
the TOTAL_CORRECTION implementation for handling OCR discrepancies.
"""
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from typing import Dict, List, Optional, Tuple


def round_money(value: Decimal) -> Decimal:
    """Round a decimal value to 2 decimal places using banker's rounding"""
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def validate_receipt_balance(receipt_data: Dict) -> Tuple[bool, Optional[Dict]]:
    """
    Validate that a receipt's numbers balance correctly.
    
    Tax and tip can be negative to represent discounts or adjustments,
    as implemented in the TOTAL_CORRECTION system for handling OCR
    discrepancies where the total doesn't match subtotal + tax + tip.
    
    Args:
        receipt_data: Dictionary containing receipt fields:
            - subtotal: Receipt subtotal (must be non-negative)
            - tax: Tax amount (can be negative for discounts)
            - tip: Tip amount (can be negative for discounts)
            - total: Total amount (must be non-negative)
            - items: List of line items with quantity, unit_price, total_price
    
    Returns:
        Tuple of (is_valid, errors_dict)
        errors_dict contains specific validation errors if any
    """
    errors = {}
    
    try:
        # Convert to Decimal for precise calculations
        subtotal = Decimal(str(receipt_data.get('subtotal', 0)))
        tax = Decimal(str(receipt_data.get('tax', 0)))
        tip = Decimal(str(receipt_data.get('tip', 0)))
        total = Decimal(str(receipt_data.get('total', 0)))
        items = receipt_data.get('items', [])
        
        # Validate individual item calculations
        items_sum = Decimal('0')
        for i, item in enumerate(items):
            if not item.get('name'):
                continue  # Skip empty items

            # Support fractional quantities
            num = int(item.get('quantity_numerator', item.get('quantity', 1)))
            den = int(item.get('quantity_denominator', 1))
            quantity = Fraction(num, den)

            unit_price = Decimal(str(item.get('unit_price', 0)))
            item_total = Decimal(str(item.get('total_price', 0)))

            expected_total = (Decimal(quantity.numerator) / Decimal(quantity.denominator)) * unit_price

            # Allow for small rounding differences (within 1 cent)
            if abs(expected_total - item_total) > Decimal('0.01'):
                if 'items' not in errors:
                    errors['items'] = []
                qty_display = f"{num}/{den}" if den > 1 else str(num)
                errors['items'].append({
                    'index': i,
                    'name': item.get('name'),
                    'message': f"Item total ${item_total:.2f} doesn't match quantity ({qty_display}) × price (${unit_price:.2f}) = ${expected_total:.2f}"
                })

            items_sum += item_total
        
        # Check if items sum matches subtotal (allow 1 cent tolerance for rounding)
        if abs(items_sum - subtotal) > Decimal('0.01'):
            errors['subtotal'] = f"Subtotal ${subtotal:.2f} doesn't match sum of items ${items_sum:.2f}"
        
        # Check if subtotal + tax + tip = total (allow 1 cent tolerance)
        calculated_total = subtotal + tax + tip
        if abs(calculated_total - total) > Decimal('0.01'):
            errors['total'] = f"Total ${total:.2f} doesn't match subtotal (${subtotal:.2f}) + tax (${tax:.2f}) + tip (${tip:.2f}) = ${calculated_total:.2f}"
        
        # Check for negative values
        # Note: Tax and tip CAN be negative (representing discounts)
        # as per TOTAL_CORRECTION implementation for handling discrepancies
        if subtotal < 0:
            errors['subtotal_negative'] = "Subtotal cannot be negative"
        # Allow negative tax (discount/credit)
        # Allow negative tip (discount/credit)
        if total < 0:
            errors['total_negative'] = "Total cannot be negative"
        
        # Check for unreasonable values
        if total > 10000:
            errors['total_high'] = "Total exceeds reasonable limit ($10,000)"
        
        # Tax should generally be less than 20% of subtotal (but this is a warning, not an error)
        if subtotal > 0 and tax > subtotal * Decimal('0.20'):
            if 'warnings' not in errors:
                errors['warnings'] = []
            errors['warnings'].append(f"Tax (${tax:.2f}) is more than 20% of subtotal (${subtotal:.2f})")
        
        # Tip should generally be less than 100% of subtotal (warning)
        if subtotal > 0 and tip > subtotal:
            if 'warnings' not in errors:
                errors['warnings'] = []
            errors['warnings'].append(f"Tip (${tip:.2f}) is more than 100% of subtotal (${subtotal:.2f})")
        
    except (TypeError, ValueError, KeyError) as e:
        errors['parse_error'] = f"Invalid data format: {str(e)}"
    
    is_valid = not any(key not in ['warnings'] for key in errors.keys())
    
    return is_valid, errors if errors else None


def calculate_prorations(subtotal: Decimal, tax: Decimal, tip: Decimal, 
                         item_total: Decimal) -> Dict[str, Decimal]:
    """
    Calculate prorated tax and tip for a line item.
    
    Args:
        subtotal: Receipt subtotal
        tax: Total tax amount
        tip: Total tip amount
        item_total: Line item total
    
    Returns:
        Dictionary with 'tax', 'tip', and 'total_share' amounts
    """
    if subtotal == 0:
        return {
            'tax': Decimal('0'),
            'tip': Decimal('0'), 
            'total_share': item_total
        }
    
    proportion = item_total / subtotal
    prorated_tax = tax * proportion
    prorated_tip = tip * proportion
    total_share = item_total + prorated_tax + prorated_tip
    
    return {
        'tax': round_money(prorated_tax),
        'tip': round_money(prorated_tip),
        'total_share': round_money(total_share)
    }