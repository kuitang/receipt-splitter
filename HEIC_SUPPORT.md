# HEIC Support Implementation

## Summary
HEIC/HEIF image format support has been implemented with automatic conversion to JPEG for browser compatibility. Users can upload HEIC files directly from iPhones, and the system automatically converts them to JPEG for display while preserving the original for OCR processing.

## Changes Made

### 1. Frontend (HTML)
**File:** `templates/receipts/index.html`

- Updated `accept` attribute to explicitly include HEIC formats:
  ```html
  accept="image/*,.heic,.heif,image/heic,image/heif"
  ```
- Updated help text to mention HEIC/HEIF support
- Added JavaScript validation for HEIC file extensions
- Added real-time file selection feedback

### 2. Backend (Django)
**Files:** 
- `receipts/image_utils.py` - New utility module for image conversion
- `receipts/async_processor.py` - Converts HEIC to JPEG for storage
- `receipts/ocr_service.py` - Processes original HEIC for OCR

Key features:
- Automatic HEIC to JPEG conversion for browser display
- Original HEIC bytes sent to OpenAI for best OCR quality
- Supports HEIC, HEIF, JPEG, PNG, WebP formats
- Proper handling of HEIC bytes through pillow-heif

### 3. OCR Library
**File:** `ocr_lib.py`

- Already supported HEIC through PIL with pillow-heif
- Handles automatic image conversion for OpenAI API

### 4. Dependencies
**File:** `requirements.txt`

- Added `pillow-heif==1.1.0` for HEIC image processing
- Updated documentation to include this dependency

## Testing

### Test Files Created
1. `integration_test/test_image_formats.py` - Tests all image format support
2. `integration_test/test_frontend_heic.py` - Specifically tests frontend HEIC support

### Test Results
✅ All tests pass:
- HEIC files can be selected in browser file picker
- HEIC files upload successfully
- OCR correctly processes HEIC images
- The Gin Mill receipt (IMG_6839.HEIC) is correctly extracted

## User Experience

Users will now experience:
1. **File Selection**: HEIC files appear as selectable in the file picker (not grayed out)
2. **Visual Feedback**: Selected HEIC file info is displayed before upload
3. **Validation**: Client-side validation accepts HEIC files
4. **Automatic Conversion**: HEIC files are converted to JPEG for browser display
5. **Processing**: Server correctly processes original HEIC images through OCR
6. **Results**: Same accuracy as JPEG/PNG images
7. **Browser Compatibility**: Converted JPEG images display correctly in all browsers including Chrome

## Browser Compatibility

The implementation works across all modern browsers:
- **Safari/iOS**: Native HEIC support, files directly selectable
- **Chrome**: HEIC files can be selected and uploaded, converted JPEG displayed
- **Firefox**: HEIC files can be selected and uploaded, converted JPEG displayed
- **Edge**: Full support through the accept attribute, converted JPEG displayed

Note: While Chrome cannot natively display HEIC images, our automatic conversion to JPEG ensures all uploaded receipts are viewable.

## Technical Details

### Why This Was Needed
- Default `accept="image/*"` doesn't recognize HEIC on some browsers
- Safari particularly needs explicit HEIC in accept attribute
- iPhone users couldn't upload photos without converting first

### How It Works
1. Browser file picker shows HEIC files due to explicit accept values
2. JavaScript validates the file extension and size
3. Django backend detects HEIC format from filename
4. HEIC is converted to JPEG for storage using pillow-heif
5. Original HEIC bytes are sent to OpenAI Vision API for OCR
6. Converted JPEG is stored and served to browsers for display

## Performance
- HEIC files are typically 50% smaller than JPEG
- Faster uploads due to smaller file size
- No quality loss in OCR accuracy
- Processing time similar to other formats

## Future Enhancements
- Could add client-side HEIC preview
- Could show HEIC compression savings to user
- Could auto-rotate based on EXIF data (already implemented)