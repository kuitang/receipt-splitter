# Communist Style - Smart Receipt Splitter

Django web app for splitting bills based on actual consumption using OCR. No accounts required, data expires after 30 days.

## Quick Start

```bash
python3 -m venv venv && source venv/bin/activate
pip install django pillow pillow-heif channels daphne openai
export OPENAI_API_KEY=your_key_here  # Optional, uses mock data without it
python manage.py migrate
python manage.py runserver
```

Visit http://localhost:8000

## Testing

```bash
python manage.py test receipts -v 2  # All 15 tests should pass
python integration_test/run_tests.sh  # Integration tests
```

## Key Features

- **OCR Receipt Scanning** - Upload photo → auto-extract items/prices
- **Multiple Formats** - JPEG, PNG, HEIC/HEIF, WebP supported  
- **Fair Splitting** - Proportional tax/tip based on actual orders
- **Session-based** - No accounts, 6-char slugs for easy sharing
- **Mobile Optimized** - HTMX + Tailwind CSS responsive design
- **Privacy First** - 30-day expiry, images in memory cache only

## Workflow

1. **Upload** → OCR processing → editable receipt
2. **Edit** → validate/correct extracted data  
3. **Finalize** → generate shareable URL
4. **Claim** → friends select items → see individual totals

## Architecture

- **Django 5.2.5** - Backend with SQLite database
- **OpenAI Vision API** - Receipt OCR processing
- **Session-based auth** - Edit tokens, no user registration
- **Rate limiting** - 10/min upload, 30/min update, 15/min claim
- **Security** - UUID4 + slug URLs, input validation, XSS protection

See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details.