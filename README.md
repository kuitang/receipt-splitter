# Communist Style - Smart Receipt Splitter

An ironically named web application that helps groups split bills based on actual consumption rather than equally. Uses OCR technology to digitize receipts and provides a frictionless, account-free experience.

## Features

- 📸 **OCR Receipt Scanning** - Upload a photo and automatically extract items
- 🖼️ **Multiple Image Formats** - Supports JPEG, PNG, HEIC/HEIF, and WebP
- ✏️ **Edit & Verify** - Review and correct extracted data before sharing
- 🔗 **Easy Sharing** - Generate secure links with QR codes
- 💰 **Fair Splitting** - Each person pays for what they ordered plus proportional tax/tip
- 📱 **Mobile Optimized** - Works seamlessly on all devices
- 🔒 **Privacy First** - No accounts required, data expires after 30 days

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key (optional, uses mock data without it)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/receipt-splitter.git
cd receipt-splitter
```

2. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install django python-dotenv pillow pillow-heif channels daphne openai
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Start the development server:
```bash
python manage.py runserver
```

7. Visit http://localhost:8000

## Running Tests

```bash
python manage.py test receipts -v 2
```

All 15 tests should pass.

## Generating Sample Images

To generate sample images using DALL-E:

```bash
python generate_images.py
```

Note: Requires valid OPENAI_API_KEY in .env

## Project Structure

- `receipts/` - Main Django app with models, views, and OCR service
- `templates/` - HTML templates with HTMX integration
- `static/` - CSS and JavaScript files
- `media/` - User uploaded receipts and generated images

## Technology Stack

- **Backend**: Django 5.2.5
- **Database**: SQLite (development)
- **Frontend**: HTMX + Tailwind CSS
- **OCR**: OpenAI Vision API
- **Real-time**: Django Channels (configured)

## How It Works

1. **Upload** - Take a photo of your receipt
2. **Process** - OCR extracts items, prices, tax, and tip
3. **Edit** - Review and correct any extraction errors
4. **Share** - Get a link to send to your group
5. **Claim** - Friends select what they ordered
6. **Split** - Everyone sees their fair share including tax/tip

## API Endpoints

- `POST /upload/` - Upload receipt image
- `GET /r/{uuid}/` - View receipt
- `POST /claim/{uuid}/` - Claim items
- `POST /finalize/{uuid}/` - Finalize receipt

## Development

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design details.

See [LOG.md](LOG.md) for development history.

## License

MIT