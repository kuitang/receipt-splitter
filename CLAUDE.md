# CLAUDE.md

Communist Style — smart receipt splitter. Upload a photo, OCR extracts items/prices, share a link, friends claim what they ordered, everyone pays their fair share. Supports JPEG, PNG, HEIC/HEIF, WebP. No accounts — session-based with 6-char slug URLs. Data expires after 30 days.

## Development Commands

### Setup & Environment
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
DEBUG=true python3 manage.py migrate
DEBUG=true python3 manage.py runserver
# Visit http://localhost:8000
```

### Testing
```bash
# Django unit tests
DEBUG=true python3 manage.py test receipts -v 2

# Specific test module
DEBUG=true python3 manage.py test receipts.test_claim_totals

# Integration tests (requires server on localhost:8000)
cd integration_test && ./run_tests.sh          # mock OCR
cd integration_test && ./run_tests.sh --real   # real Gemini API

# JavaScript tests (always headless — interactive mode will timeout)
npm test -- --run
npm run test:coverage

# Regenerate JS test templates after changing Django templates
npm run generate-templates
```

## Architecture Overview

### Stack
- **Django 5.2.5** backend, SQLite database
- **Session-based auth** (no user accounts, edit tokens)
- **HTMX + Tailwind CSS** frontend
- **Google Gemini API** for receipt OCR (structured outputs via Pydantic)

### Key Directories
- `receipts/models.py` — Receipt, LineItem, Claim models
- `receipts/views.py` — HTTP handlers
- `receipts/services/` — Business logic (receipt_service.py, claim_service.py)
- `receipts/validation.py` — Balance validation
- `receipts/validators.py` — Input sanitization (bleach, XSS)
- `lib/ocr/` — OCR processing with Gemini structured outputs
- `templates/receipts/` — Django templates with reusable partials
- `templates/receipts/partials/js_templates.html` — `<template>` tags cloned by JS
- `static/js/` — edit-page.js, view-page.js, template-utils.js, utils.js
- `test/js/` — Vitest test suite

### Request Flow
1. **Upload** → OCR processing → Receipt creation (with optional Venmo username)
2. **Edit** → Validation pipeline → Receipt updates (fractional quantities supported)
3. **Finalize** → Generate shareable URL with 6-char slug
4. **Claim** → Session-based item claiming with shared-denominator fractions

### Data Model: Shared Denominator

LineItem has `quantity_numerator` and `quantity_denominator`. Claim has only `quantity_numerator` — the denominator is always inherited from the parent LineItem.

- Validation: `sum(claim.numerator) <= item.numerator`
- Subdivide scales all numerators proportionally (LCM-aware)
- `get_per_portion_share()` = `total_share / item.quantity_numerator`
- Share for a claim = `claim.numerator / item.numerator * total_share`

### Frontend Architecture

**Template-based pattern**: Django `<template>` tags in `js_templates.html` are cloned by `window.TemplateUtils` methods. After modifying templates, run `npm run generate-templates` to update JS test fixtures.

**JS test setup**:
```javascript
import { setupTestEnvironment, setupTemplateUtils, setBodyHTML } from './test-setup.js';
setupTestEnvironment();
await setupTemplateUtils();
beforeEach(() => setBodyHTML('<div id="container"></div>'));
```

### Security
- Rate limiting (10/min upload, 30/min update, 15/min claim)
- Content Security Policy middleware
- Input validation and XSS protection (bleach)
- Session-based edit tokens

### Environment Variables
- `GEMINI_API_KEY` — Required for real OCR, uses mock data without it
- `OPENAI_API_KEY` — Used by prompt tuning eval scripts only
- `INTEGRATION_TEST_REAL_OPENAI_OCR=true` — Use real Gemini API in integration tests (legacy env var name)
- `DEBUG=true` — Enable debug mode (required for local dev and tests)

### Deployment (Fly.io)

**IMPORTANT: Do NOT run `fly deploy` manually. Deployments happen via GitHub CI only (merge to main).**

```bash
# Debugging only — never deploy from these
fly logs -a youowe
fly status -a youowe
fly ssh console -a youowe
```

- App name: `youowe`, custom domain: `youowe.app`, region: `ord`
- Gunicorn WSGI (not Daphne) in production
- `fly.toml` sets `DEBUG=False`; secrets set via `fly secrets set`
- Release command runs migrations automatically on deploy
- Static files collected to `/code/staticfiles/` and served by Fly statics

### File Organization
- Runtime logs in `run/` directory (git-ignored)
- Images processed in memory only (no persistent storage)
- Static files served by Django in development
