# Discount and Adjustment Handling

## Overview
The receipt splitter supports negative tax and tip values to represent discounts, credits, or adjustments. This is essential for handling real-world receipts where the OCR-extracted values may not balance perfectly.

## Why Allow Negative Tax/Tip?

Based on the TOTAL_CORRECTION implementation, receipts often have discrepancies where:
- The total paid doesn't match `subtotal + tax + tip`
- Service charges or discounts are applied but not itemized
- OCR misreads or misses certain values

### Example: The Gin Mill Case
```
Items:    $60.50
Subtotal: $60.50
Tax:      $0.00
Tip:      $0.00 → Corrected to $3.50
Total:    $64.00
```

The $3.50 discrepancy is treated as an unlisted service charge/tip to make the receipt balance.

## Validation Rules

### ✅ Allowed Negative Values
- **Tax**: Can be negative (represents tax credit or discount)
- **Tip**: Can be negative (represents discount or correction)

### ❌ Not Allowed Negative Values
- **Subtotal**: Must be non-negative (items can't have negative total)
- **Total**: Must be non-negative (can't pay negative amount)

## Use Cases

### 1. Promotional Discounts
```
Subtotal: $50.00
Tax:      $5.00
Tip:      -$10.00  (10% off promotion)
Total:    $45.00
```

### 2. Tax Credits
```
Subtotal: $100.00
Tax:      -$5.00   (tax credit applied)
Tip:      $15.00
Total:    $110.00
```

### 3. OCR Correction
When TOTAL_CORRECTION detects a discrepancy:
- If total is higher than expected → adds to tip
- If total is lower than expected → creates negative tip (discount)

## Implementation

### Backend (`validation.py`)
```python
# Tax and tip CAN be negative (representing discounts)
# as per TOTAL_CORRECTION implementation
if subtotal < 0:
    errors['subtotal_negative'] = "Subtotal cannot be negative"
# Allow negative tax (discount/credit)
# Allow negative tip (discount/credit)
if total < 0:
    errors['total_negative'] = "Total cannot be negative"
```

### Frontend (JavaScript)
```javascript
// Note: Tax and tip CAN be negative (representing discounts)
// as per TOTAL_CORRECTION implementation
if (data.subtotal < 0) errors.push("Subtotal cannot be negative");
// Tax can be negative (discount/credit)
// Tip can be negative (discount/credit)
if (data.total < 0) errors.push("Total cannot be negative");
```

## Invariant Maintained
The fundamental equation must always hold:
```
subtotal + tax + tip = total
```

This ensures fair and accurate bill splitting regardless of discounts or adjustments.