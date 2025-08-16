# System Architecture

## Key Files & Locations

### Core Application
- **models.py:18** - Receipt model with UUID/slug, 30-day expiry
- **models.py:77** - LineItem with prorated tax/tip calculations  
- **models.py:111** - Claim model with 30-second grace period
- **views.py:66** - upload_receipt with OCR processing
- **views.py:136** - update_receipt with validation
- **views.py:253** - view_receipt with claiming interface
- **ocr_service.py** - OpenAI Vision API integration via lib/ocr/

### URL Routing
- **urls.py** - Dual UUID/slug support for backward compatibility
- **receipt_splitter/urls.py** - Main project routing

### Configuration
- **settings.py** - Django config with rate limiting, security headers
- **CLAUDE.md** - Development instructions and workflow

## Technology Stack
- Django 5.2.5, SQLite, HTMX + Tailwind CSS
- OpenAI Vision API (GPT-4o), DALL-E 3 for images
- Session-based auth, no user accounts required

## Data Flow
1. Upload → OCR processing → placeholder receipt with slug
2. Edit → validation → save (allows invalid data) 
3. Finalize → validation required → shareable URL
4. Claim → name entry → item selection → 30s undo window

## Security Features
- UUID4 + 6-char slug for receipt URLs
- Session-based access control with edit tokens  
- Rate limiting (10/min upload, 30/min update, 15/min claim)
- Input validation and XSS protection
- Images stored in memory cache, not filesystem

## API Endpoints
- POST /upload/ → creates receipt, returns edit URL
- GET /r/{slug}/ → view/claim interface
- POST /update/{slug}/ → save changes (edit permission required)
- POST /finalize/{slug}/ → lock receipt (uploader only)
- POST /claim/{slug}/ → claim items (session-based)

## Testing & Validation
- Unit tests in receipts/tests.py (15 tests)
- Integration tests in integration_test/
- Balance validation prevents finalization of unbalanced receipts