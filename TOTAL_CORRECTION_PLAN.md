# Receipt Total Correction Plan

## Problem Statement
OCR may extract values where `subtotal + tax + tip ≠ total`. Example from The Gin Mill receipt:
- Items sum: $60.50
- Subtotal: $60.50
- Tax: $0.00
- Tip: $0.00
- **Total: $64.00** (Discrepancy: $3.50)

## Invariant to Enforce
**Line items MUST add up to the Total amount paid**

## Correction Algorithm

### Principles
1. **Total is truth**: The receipt total is what was actually paid
2. **Preserve items**: Never modify individual line items (they're usually correct)
3. **Smart distribution**: Allocate discrepancies intelligently

### Algorithm Steps

```python
def correct_totals(items_sum, subtotal, tax, tip, total):
    # Calculate discrepancy
    calculated_total = subtotal + tax + tip
    discrepancy = total - calculated_total
    
    if abs(discrepancy) < 0.01:  # No correction needed
        return subtotal, tax, tip
    
    # Case 1: Tax and tip are both zero - treat discrepancy as service charge/tip
    if tax == 0 and tip == 0:
        # Assume discrepancy is an unlisted service charge or tip
        tip = discrepancy
        return subtotal, tax, tip
    
    # Case 2: Tax or tip exists - proportionally adjust
    if tax > 0 or tip > 0:
        # Distribute discrepancy proportionally
        tax_ratio = tax / (tax + tip) if (tax + tip) > 0 else 0.5
        tip_ratio = tip / (tax + tip) if (tax + tip) > 0 else 0.5
        
        tax += discrepancy * tax_ratio
        tip += discrepancy * tip_ratio
        
        # Ensure non-negative
        tax = max(0, tax)
        tip = max(0, tip)
        
        return subtotal, tax, tip
    
    # Case 3: Subtotal doesn't match items
    if abs(items_sum - subtotal) > 0.01:
        # Adjust subtotal to match items
        subtotal = items_sum
        # Recalculate with new subtotal
        return correct_totals(items_sum, subtotal, tax, tip, total)
```

### Edge Cases

1. **Negative discrepancy**: Could be a discount not reflected in items
2. **Large discrepancy**: May indicate OCR error - flag for review
3. **Zero total**: Invalid receipt
4. **Missing total**: Use calculated total

## Implementation Location

1. Add `correct_totals()` method to `ReceiptData` class in `ocr_lib.py`
2. Call automatically after OCR extraction
3. Log corrections for transparency
4. Include correction details in response

## Testing Strategy

1. **Unit tests** for correction algorithm with various scenarios:
   - Zero tax/tip with discrepancy (The Gin Mill case)
   - Non-zero tax/tip with discrepancy
   - Negative discrepancy (discount)
   - Perfect match (no correction)

2. **Integration test** with real receipt data

## Expected Outcome

For The Gin Mill receipt:
- Before: subtotal=$60.50, tax=$0, tip=$0, total=$64.00
- After: subtotal=$60.50, tax=$0, tip=$3.50, total=$64.00
- Result: Discrepancy treated as tip/service charge