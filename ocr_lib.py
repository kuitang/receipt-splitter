"""
OCR Library for Receipt Processing using OpenAI Vision API
"""

import base64
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import re

from PIL import Image
import pillow_heif
from openai import OpenAI

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)


@dataclass
class LineItem:
    """Represents a single line item on a receipt"""
    name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'total_price': float(self.total_price)
        }


@dataclass
class ReceiptData:
    """Structured receipt data extracted from image"""
    restaurant_name: str
    date: datetime
    items: List[LineItem]
    subtotal: Decimal
    tax: Decimal
    tip: Decimal
    total: Decimal
    confidence_score: float = 0.0
    raw_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'restaurant_name': self.restaurant_name,
            'date': self.date.isoformat() if self.date else None,
            'items': [item.to_dict() for item in self.items],
            'subtotal': float(self.subtotal),
            'tax': float(self.tax),
            'tip': float(self.tip),
            'total': float(self.total),
            'confidence_score': self.confidence_score,
            'raw_text': self.raw_text
        }
    
    def validate(self) -> tuple[bool, List[str]]:
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
        
        # Check for negative values
        if any(x < 0 for x in [self.subtotal, self.tax, self.total]):
            errors.append("Negative values found in receipt totals")
        
        # Check for reasonable values
        if self.total > Decimal('10000'):
            errors.append("Total seems unreasonably high (>$10,000)")
        
        return len(errors) == 0, errors


class ReceiptOCR:
    """Main OCR class for processing receipt images"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """
        Initialize the OCR processor
        
        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (default: gpt-4o for vision)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_image_size = 2048  # Max dimension in pixels
        self.jpeg_quality = 85
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR results
        
        Args:
            image: PIL Image object
            
        Returns:
            Processed PIL Image
        """
        # Convert to RGB if necessary
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        # Auto-rotate based on EXIF
        try:
            from PIL import ImageOps
            image = ImageOps.exif_transpose(image)
        except Exception as e:
            logger.debug(f"Could not auto-rotate image: {e}")
        
        # Resize if too large
        if max(image.size) > self.max_image_size:
            image.thumbnail((self.max_image_size, self.max_image_size), Image.Resampling.LANCZOS)
            logger.info(f"Resized image to {image.size}")
        
        return image
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=self.jpeg_quality)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def _create_prompt(self) -> str:
        """Create the prompt for OpenAI Vision API"""
        return """Analyze this receipt image and extract ALL information in the following JSON format:

{
    "restaurant_name": "string - name of the restaurant/merchant",
    "date": "string - date in YYYY-MM-DD format, use today if not visible",
    "items": [
        {
            "name": "string - item name",
            "quantity": "integer - quantity (default 1 if not specified)",
            "unit_price": "number - price per unit",
            "total_price": "number - total price for this line item"
        }
    ],
    "subtotal": "number - subtotal before tax and tip",
    "tax": "number - tax amount (0 if not shown)",
    "tip": "number - tip amount (0 if not shown)",
    "total": "number - final total amount",
    "confidence_score": "number between 0-1 - your confidence in the extraction",
    "notes": "string - any issues or ambiguities noticed"
}

IMPORTANT INSTRUCTIONS:
1. Extract EVERY line item you can see, even if partially visible
2. If quantity is not shown, assume 1
3. Ensure all monetary values are positive numbers with 2 decimal places
4. If you see service charge, include it in the tip field
5. If subtotal is not explicitly shown, calculate it from items
6. The sum of items should equal subtotal (or be very close)
7. Subtotal + tax + tip should equal total (or be very close)
8. Use 0 for missing tax or tip rather than null
9. Set confidence_score based on image quality and extraction certainty

Return ONLY valid JSON, no other text."""
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the API response to extract JSON data"""
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                logger.debug(f"JSON string: {json_str}")
                raise ValueError(f"Invalid JSON in response: {e}")
        else:
            raise ValueError("No JSON found in response")
    
    def _data_to_receipt(self, data: Dict[str, Any], raw_text: str) -> ReceiptData:
        """Convert parsed data to ReceiptData object"""
        # Parse date
        date_str = data.get('date', '')
        try:
            if date_str:
                date = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                date = datetime.now()
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}, using today")
            date = datetime.now()
        
        # Parse items
        items = []
        for item_data in data.get('items', []):
            try:
                item = LineItem(
                    name=item_data.get('name', 'Unknown Item'),
                    quantity=int(item_data.get('quantity', 1)),
                    unit_price=Decimal(str(item_data.get('unit_price', 0))),
                    total_price=Decimal(str(item_data.get('total_price', 0)))
                )
                items.append(item)
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid item: {item_data}, error: {e}")
        
        # Create receipt data
        receipt = ReceiptData(
            restaurant_name=data.get('restaurant_name', 'Unknown Restaurant'),
            date=date,
            items=items,
            subtotal=Decimal(str(data.get('subtotal', 0))),
            tax=Decimal(str(data.get('tax', 0))),
            tip=Decimal(str(data.get('tip', 0))),
            total=Decimal(str(data.get('total', 0))),
            confidence_score=float(data.get('confidence_score', 0.5)),
            raw_text=raw_text
        )
        
        return receipt
    
    def process_image(self, image_path: Union[str, Path]) -> ReceiptData:
        """
        Process a receipt image file
        
        Args:
            image_path: Path to the image file
            
        Returns:
            ReceiptData object with extracted information
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        logger.info(f"Processing image: {image_path}")
        
        # Load and preprocess image
        try:
            image = Image.open(image_path)
            image = self._preprocess_image(image)
        except Exception as e:
            raise ValueError(f"Failed to load/process image: {e}")
        
        # Convert to base64
        base64_image = self._image_to_base64(image)
        
        # Call OpenAI API
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self._create_prompt()},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content
            logger.debug(f"API Response: {response_text}")
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise ValueError(f"Failed to process image with OpenAI: {e}")
        
        # Parse response
        try:
            data = self._parse_response(response_text)
            receipt = self._data_to_receipt(data, response_text)
            
            # Validate the data
            is_valid, errors = receipt.validate()
            if not is_valid:
                logger.warning(f"Validation issues: {errors}")
            
            return receipt
            
        except Exception as e:
            logger.error(f"Failed to parse OCR response: {e}")
            raise ValueError(f"Failed to parse OCR results: {e}")
    
    def process_image_bytes(self, image_bytes: bytes, format: str = "JPEG") -> ReceiptData:
        """
        Process receipt image from bytes
        
        Args:
            image_bytes: Image data as bytes
            format: Image format (JPEG, PNG, etc.)
            
        Returns:
            ReceiptData object with extracted information
        """
        try:
            image = Image.open(BytesIO(image_bytes))
            image = self._preprocess_image(image)
        except Exception as e:
            raise ValueError(f"Failed to load image from bytes: {e}")
        
        # Convert to base64
        base64_image = self._image_to_base64(image)
        
        # Rest is the same as process_image
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self._create_prompt()},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content
            logger.debug(f"API Response: {response_text}")
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise ValueError(f"Failed to process image with OpenAI: {e}")
        
        # Parse response
        try:
            data = self._parse_response(response_text)
            receipt = self._data_to_receipt(data, response_text)
            
            # Validate the data
            is_valid, errors = receipt.validate()
            if not is_valid:
                logger.warning(f"Validation issues: {errors}")
            
            return receipt
            
        except Exception as e:
            logger.error(f"Failed to parse OCR response: {e}")
            raise ValueError(f"Failed to parse OCR results: {e}")