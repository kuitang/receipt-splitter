"""
Pydantic models for receipt data validation and serialization
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from decimal import Decimal
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class LineItem(BaseModel):
    """Represents a single line item on a receipt"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str
    quantity: int = Field(default=1, ge=1)
    unit_price: Decimal = Field(ge=0)
    total_price: Decimal = Field(ge=0)
    
    @field_validator('unit_price', 'total_price', mode='before')
    @classmethod
    def coerce_to_decimal(cls, v):
        """Convert float/int/str to Decimal"""
        if isinstance(v, (int, float, str)):
            return Decimal(str(v))
        return v
    
    @field_validator('total_price', mode='after')
    @classmethod
    def validate_total(cls, v, info):
        """Auto-correct total price if it doesn't match quantity * unit_price"""
        quantity = info.data.get('quantity', 1)
        unit_price = info.data.get('unit_price', Decimal('0'))
        expected = Decimal(str(quantity)) * unit_price
        
        # Allow small tolerance for rounding
        if abs(v - expected) > Decimal('0.01'):
            logger.debug(f"Correcting item total from {v} to {expected}")
            return expected
        return v
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Django compatibility"""
        return {
            'name': self.name,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'total_price': float(self.total_price)
        }


class ReceiptData(BaseModel):
    """Structured receipt data extracted from image"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    restaurant_name: str
    date: datetime
    items: List[LineItem]
    subtotal: Decimal = Field(ge=0)
    tax: Decimal = Field(ge=0)
    tip: Decimal  # Can be negative for discounts
    total: Decimal = Field(ge=0)
    confidence_score: float = Field(ge=0, le=1, default=0.5)
    notes: Optional[str] = None
    
    # For backwards compatibility
    raw_text: Optional[str] = None
    
    @field_validator('date', mode='before')
    @classmethod
    def parse_date(cls, v):
        """Parse date from various formats"""
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Try ISO format first
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except:
                pass
            # Try YYYY-MM-DD format
            try:
                return datetime.strptime(v, '%Y-%m-%d')
            except:
                pass
            # Try other common formats
            for fmt in ['%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                try:
                    return datetime.strptime(v, fmt)
                except:
                    continue
        # Default to today if can't parse
        logger.warning(f"Could not parse date: {v}, using today")
        return datetime.now()
    
    @field_validator('subtotal', 'tax', 'tip', 'total', mode='before')
    @classmethod
    def coerce_to_decimal(cls, v):
        """Convert float/int/str to Decimal"""
        if isinstance(v, (int, float, str)):
            return Decimal(str(v))
        return v
    
    def validate_totals(self) -> tuple[bool, List[str]]:
        """Validate the receipt data for consistency"""
        errors = []
        
        # Check if items sum to subtotal (with tolerance)
        items_sum = sum(item.total_price for item in self.items)
        if abs(items_sum - self.subtotal) > Decimal('0.10'):
            errors.append(f"Items sum ({items_sum}) doesn't match subtotal ({self.subtotal})")
        
        # Check if subtotal + tax + tip = total (with tolerance)
        calculated_total = self.subtotal + self.tax + self.tip
        if abs(calculated_total - self.total) > Decimal('0.10'):
            errors.append(f"Calculated total ({calculated_total}) doesn't match receipt total ({self.total})")
        
        # Check for negative values (except tip which can be negative for discounts)
        if any(x < 0 for x in [self.subtotal, self.tax, self.total]):
            errors.append("Negative values found in receipt totals")
        
        # Check for reasonable values
        if self.total > Decimal('10000'):
            errors.append("Total seems unreasonably high (>$10,000)")
        
        return len(errors) == 0, errors
    
    def correct_totals(self, tolerance: Decimal = Decimal('0.01')) -> dict:
        """
        Correct receipt totals to ensure subtotal + tax + tip = total
        
        Returns dict with correction details
        """
        # Calculate items sum and current total
        items_sum = sum(item.total_price for item in self.items)
        calculated_total = self.subtotal + self.tax + self.tip
        discrepancy = self.total - calculated_total
        
        corrections = {
            'applied': False,
            'original_subtotal': float(self.subtotal),
            'original_tax': float(self.tax),
            'original_tip': float(self.tip),
            'discrepancy': float(discrepancy),
            'reason': None
        }
        
        # If totals already match, no correction needed
        if abs(discrepancy) <= tolerance:
            corrections['reason'] = 'Totals already match'
            return corrections
        
        # First ensure subtotal matches items sum
        if abs(items_sum - self.subtotal) > tolerance:
            logger.info(f"Correcting subtotal from {self.subtotal} to {items_sum} to match items")
            self.subtotal = items_sum
            # Recalculate discrepancy
            calculated_total = self.subtotal + self.tax + self.tip
            discrepancy = self.total - calculated_total
        
        # Case 1: Tax and tip are both zero - treat discrepancy as service charge/tip
        if self.tax == 0 and self.tip == 0 and discrepancy > 0:
            logger.info(f"No tax/tip found, treating ${discrepancy} discrepancy as tip/service charge")
            self.tip = discrepancy
            corrections['applied'] = True
            corrections['reason'] = 'Discrepancy treated as tip/service charge'
        
        # Case 2: Tax and/or tip exist - proportionally adjust
        elif self.tax > 0 or self.tip > 0:
            tax_tip_sum = self.tax + self.tip
            if tax_tip_sum > 0:
                tax_ratio = self.tax / tax_tip_sum
                tip_ratio = self.tip / tax_tip_sum
            else:
                tax_ratio = Decimal('0.5')
                tip_ratio = Decimal('0.5')
            
            # Distribute discrepancy proportionally
            tax_adjustment = discrepancy * tax_ratio
            tip_adjustment = discrepancy * tip_ratio
            
            self.tax += tax_adjustment
            self.tip += tip_adjustment
            
            # Ensure non-negative values for tax (tip can be negative)
            if self.tax < 0:
                # Transfer negative tax to tip
                self.tip += self.tax
                self.tax = Decimal('0')
            
            logger.info(f"Proportionally adjusted tax by {tax_adjustment} and tip by {tip_adjustment}")
            corrections['applied'] = True
            corrections['reason'] = 'Proportionally adjusted tax and tip'
        
        # Case 3: Negative discrepancy with zero tax/tip (possible discount)
        elif discrepancy < 0:
            # Create a negative tip to represent discount
            logger.info(f"Negative discrepancy of ${discrepancy}, treating as discount")
            self.tip = discrepancy  # Will be negative
            corrections['applied'] = True
            corrections['reason'] = 'Negative discrepancy treated as discount'
        
        # Record final values
        corrections['corrected_subtotal'] = float(self.subtotal)
        corrections['corrected_tax'] = float(self.tax)
        corrections['corrected_tip'] = float(self.tip)
        
        # Verify correction worked
        final_calculated = self.subtotal + self.tax + self.tip
        if abs(final_calculated - self.total) > tolerance:
            logger.warning(f"Correction failed: {final_calculated} != {self.total}")
            corrections['error'] = 'Correction did not resolve discrepancy'
        
        return corrections
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Django compatibility"""
        return {
            'restaurant_name': self.restaurant_name,
            'date': self.date.isoformat() if self.date else None,
            'items': [item.to_dict() for item in self.items],
            'subtotal': float(self.subtotal),
            'tax': float(self.tax),
            'tip': float(self.tip),
            'total': float(self.total),
            'confidence_score': self.confidence_score,
            'raw_text': self.raw_text or ""
        }