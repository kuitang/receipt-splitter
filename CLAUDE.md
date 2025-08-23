# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup & Environment
```bash
# Install dependencies (virtual environment already activated)
pip install -r requirements.txt

# Database migrations
python3 manage.py migrate

# Start development server (usually already running)
python3 manage.py runserver
```

### Testing
```bash
# Run Django unit tests (all should pass)
python3 manage.py test receipts -v 2

# Run specific test module
python3 manage.py test receipts.test_claim_totals

# Integration tests with mock OCR (requires server running on localhost:8000)
cd integration_test && ./run_tests.sh

# Integration tests with real OpenAI API
cd integration_test && ./run_tests.sh --real

# JavaScript tests (always run headless to avoid timeout)
npm test -- --run           # Vitest test suite (headless)
npm run test:watch          # Watch mode
npm run test:coverage       # Coverage report
npm run test:ui             # UI test runner

# IMPORTANT: Default 'npm test' is interactive and will timeout after 2min waiting for input
# Always use 'npm test -- --run' or set CI=true environment variable

# Generate test templates for JavaScript tests
npm run generate-templates  # Same as: python3 manage.py generate_test_templates
```

### Frontend Development
```bash
# Browser-based JavaScript tests (requires server running)
# Visit: http://localhost:8000/static/run_tests.html
npm run test:browser

# Legacy JavaScript tests
npm run test:legacy
```

## Architecture Overview

### Core Application Structure
- **Django 5.2.5** backend with SQLite database
- **Session-based authentication** (no user accounts, edit tokens)
- **HTMX + Tailwind CSS** frontend with progressive enhancement
- **OpenAI Vision API** for receipt OCR processing

### Key Directories & Files
- `receipts/models.py` - Django models (Receipt, LineItem, Claim)
- `receipts/views.py` - HTTP request handlers
- `receipts/services/` - Business logic (receipt_service.py, claim_service.py)
- `receipts/repositories/` - Data access layer
- `lib/ocr/` - OCR processing with caching and structured outputs
- `templates/receipts/` - Django templates with reusable partials
- `static/js/` - JavaScript modules (edit-page.js, view-page.js, utils.js)
- `integration_test/` - Full-stack integration tests
- `test/js/` - JavaScript unit tests with Vitest

### Request Flow
1. **Upload** → OCR processing → Receipt creation
2. **Edit** → Validation pipeline → Receipt updates  
3. **Finalize** → Generate shareable URL with 6-char slug
4. **Claim** → Session-based item claiming by participants

### Testing Strategy
- **Django unit tests**: Core business logic and models
- **Integration tests**: Full HTTP workflow with mock/real OCR
- **JavaScript tests**: Frontend components and interactions
- Runtime logs stored in `run/` directory (excluded from git)

### Security Features
- Rate limiting (10/min upload, 30/min update, 15/min claim)
- Content Security Policy middleware  
- Input validation and XSS protection
- UUID4-based slugs for receipt URLs
- Session-based edit tokens

## Additional Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed file locations and system architecture
- **[PRD_IMPROVED.md](PRD_IMPROVED.md)** - Product requirements document
- **[README.md](README.md)** - User-facing setup and features overview

## Development Notes

### OCR Processing
- Uses OpenAI Vision API with structured outputs via Pydantic models
- Mock data available for testing without API costs
- Test image: `lib/ocr/test_data/IMG_6839.HEIC` with hardcoded results
- Response caching system for API efficiency

### File Organization
- Runtime logs and temp data in `run/` directory (git-ignored)
- Images processed in memory only (no persistent storage)
- Static files served by Django in development

### Environment Variables
- `OPENAI_API_KEY` - Optional, uses mock data without it  
- `INTEGRATION_TEST_REAL_OPENAI_OCR=true` - Use real API in tests
- `DEBUG=true` - Enable debug mode for testing