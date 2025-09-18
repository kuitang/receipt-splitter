# System Architecture

## File Location Guide

### Core Application Logic
- **receipts/models.py** - Django models (Receipt, LineItem, Claim)
- **receipts/views.py** - HTTP request handlers 
- **receipts/urls.py** - URL routing patterns

### Service Layer (Business Logic)
- **receipts/services/receipt_service.py** - Receipt operations
- **receipts/services/claim_service.py** - Claim management
- **receipts/services/validation_pipeline.py** - Centralized validation

### Data Access Layer
- Services directly access Django models (no repository pattern implemented)

### OCR & Image Processing
- **receipts/ocr_service.py** - Django integration for OCR
- **receipts/async_processor.py** - Background OCR processing
- **receipts/image_utils.py** - Image compression/validation
- **lib/ocr/models.py** - Pydantic models for receipt validation
- **lib/ocr/ocr_lib.py** - OpenAI Vision API with structured outputs & caching
- **lib/ocr/test_data/** - IMG_6839.HEIC test image for hardcoded results

### Frontend Assets
- **templates/receipts/** - Django templates (index, view, edit)
- **static/js/** - JavaScript modules (edit-page, view-page, utils)
- **static/css/styles.css** - Tailwind CSS styles

### Configuration & Security
- **receipt_splitter/settings.py** - Django settings
- **receipts/middleware/csp_middleware.py** - Content Security Policy
- **receipts/middleware/session_middleware.py** - Session handling
- **receipts/validators.py** - Legacy validation (being deprecated)
- **receipts/validation.py** - Additional validation rules

### Testing
- **receipts/tests.py** - Main unit tests
- **receipts/test_*.py** - Individual test modules (claim_totals, image_memory, etc.)
- **receipts/test_modules/** - Additional test modules
- **integration_test/test_*.py** - Pytest integration suites (workflow, claims, UI)
- **lib/ocr/tests/** - OCR unit tests
- **test/js/** - JavaScript tests with Vitest

### Deployment
- **Dockerfile** - Container configuration
- **fly.toml** - Fly.io deployment config
- **requirements.txt** - Python dependencies

## Technology Stack
- **Backend**: Django 5.2.5 + SQLite
- **Frontend**: HTMX + Tailwind CSS
- **OCR**: OpenAI Vision API (GPT-4o)
- **Hosting**: Fly.io
- **Auth**: Session-based (no user accounts)

## Request Flow
1. **Upload**: views.py → async_processor.py → ocr_service.py → Receipt created
2. **Edit**: views.py → ReceiptService → ValidationPipeline → Django ORM
3. **Claim**: views.py → ClaimService → Django ORM
4. **View**: views.py → Templates with session-based permissions

## Key Design Patterns
- **Service Layer**: Business logic separated from views
- **Direct ORM Access**: Services use Django ORM directly
- **Validation Pipeline**: Centralized validation logic
- **Session-based Auth**: Edit tokens and viewer names in sessions