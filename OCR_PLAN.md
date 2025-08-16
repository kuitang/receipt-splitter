# OCR Implementation Plan

## Overview
Implement a robust OCR system using OpenAI's Vision API to extract structured data from receipt images.

## Architecture

### 1. OCR Library (`ocr_lib.py`)
A standalone library with clean API that handles:
- Image format conversion (HEIC → JPEG)
- Image preprocessing (resize, enhance)
- OpenAI Vision API calls
- Response parsing and validation
- Error handling and retries

### 2. Library API Design
```python
class ReceiptOCR:
    def __init__(self, api_key: str)
    def process_image(self, image_path: str) -> ReceiptData
    def process_image_bytes(self, image_bytes: bytes, format: str) -> ReceiptData

class ReceiptData:
    restaurant_name: str
    date: datetime
    items: List[LineItem]
    subtotal: Decimal
    tax: Decimal
    tip: Decimal
    total: Decimal
    confidence_score: float
    
class LineItem:
    name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
```

### 3. Implementation Steps

#### Phase 1: Core Library
1. Image handling with Pillow
2. HEIC conversion support
3. Base64 encoding for API
4. OpenAI Vision API integration
5. Structured prompt engineering

#### Phase 2: Testing
1. Driver script (`test_ocr.py`)
2. Test with IMG_6839.HEIC
3. Log results and confidence
4. Handle edge cases

#### Phase 3: Integration
1. Update Django ocr_service.py
2. Add error handling
3. Add validation
4. Unit tests

## Key Features

### Image Preprocessing
- Auto-rotate based on EXIF
- Resize if too large (max 2048px)
- Enhance contrast for better OCR
- Support HEIC, JPEG, PNG, WebP

### Prompt Engineering
- Structured JSON output request
- Include examples in prompt
- Request confidence scores
- Handle multiple receipt formats

### Error Handling
- Retry logic for API failures
- Fallback for poor quality images
- Validation of extracted data
- User-friendly error messages

### Data Validation
- Verify subtotal + tax + tip = total
- Check for reasonable values
- Validate date formats
- Ensure items sum to subtotal

## Testing Strategy

### Unit Tests
- Mock OpenAI API responses
- Test data validation logic
- Test image preprocessing
- Test error handling

### Integration Tests
- Real API calls with test image
- End-to-end receipt processing
- Various image formats
- Edge cases (blurry, rotated, etc.)

## Success Criteria
1. Successfully extract data from IMG_6839.HEIC
2. Accurate item detection (>90% accuracy)
3. Correct total calculations
4. Handle various receipt formats
5. Graceful error handling