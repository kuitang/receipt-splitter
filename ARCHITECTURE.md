# System Architecture

## Overview

Communist Style is a Django-based web application for splitting restaurant bills based on actual consumption. The system uses OCR to digitize receipts and provides a frictionless, account-free experience.

## Technology Stack

- **Backend**: Django 5.2.5
- **Database**: SQLite (dev) / PostgreSQL (prod ready)
- **Frontend**: Server-side rendering with HTMX + Tailwind CSS
- **OCR**: OpenAI Vision API (GPT-4o)
- **Real-time**: Django Channels (configured, not yet implemented)
- **Image Generation**: OpenAI DALL-E 3

## Project Structure

```
receipt-splitter/
├── receipt_splitter/       # Django project settings
│   ├── settings.py        # Configuration with environment variables
│   ├── urls.py            # URL routing
│   ├── asgi.py            # ASGI config for Channels
│   └── wsgi.py            # WSGI config
├── receipts/              # Main application
│   ├── models.py          # Data models
│   ├── views.py           # Request handlers
│   ├── urls.py            # App URL patterns
│   ├── tests.py           # Unit tests
│   └── ocr_service.py     # OCR integration
├── templates/             # HTML templates
│   ├── base.html          # Base template
│   └── receipts/          # App templates
├── static/                # Static files (CSS, JS)
├── media/                 # User uploads
├── venv/                  # Virtual environment
└── generate_images.py     # DALL-E image generation script
```

## Data Flow

1. **Upload Flow**
   - User uploads receipt image
   - OCR service extracts structured data
   - Receipt and line items saved to database
   - User redirected to edit interface

2. **Edit Flow**
   - User reviews/modifies extracted data
   - Real-time proration calculations
   - Save changes or finalize receipt
   - Generate shareable URL

3. **Claim Flow**
   - Invitees access via UUID URL
   - Enter name (collision detection)
   - Select items to claim
   - 30-second grace period for undo

## Database Schema

### Receipt
- UUID primary key for security
- Stores totals, restaurant info, uploader name
- 30-day automatic expiration
- Finalization lock prevents editing

### LineItem
- Foreign key to Receipt
- Quantity-based items
- Prorated tax/tip calculations
- Tracks available vs claimed quantities

### Claim
- Links users to items via session
- Grace period for undo
- Quantity-based claiming
- Session-scoped identity

### ActiveViewer
- Presence tracking per receipt
- Session-based identification
- Last seen timestamp

## Security Measures

1. **URL Security**: UUID4 (cryptographically random)
2. **Session Management**: HttpOnly, Secure cookies
3. **CSRF Protection**: Django middleware
4. **Input Validation**: Server-side validation
5. **Rate Limiting**: Planned for production

## API Design

RESTful endpoints with JSON responses:
- `POST /upload/` - Receipt upload
- `GET /r/{uuid}/` - View receipt
- `POST /update/{uuid}/` - Update receipt
- `POST /finalize/{uuid}/` - Finalize receipt
- `POST /claim/{uuid}/` - Claim items
- `DELETE /unclaim/{uuid}/{id}/` - Undo claim

## Frontend Architecture

- **Server-side rendering**: Django templates
- **Progressive enhancement**: HTMX for dynamic updates
- **Styling**: Tailwind CSS via CDN
- **JavaScript**: Vanilla JS for calculations
- **Mobile-first**: Responsive design

## Deployment Considerations

1. **Environment Variables**
   - OPENAI_API_KEY
   - SECRET_KEY (production)
   - DATABASE_URL (production)

2. **Static Files**
   - WhiteNoise or CDN for production
   - Media storage for receipts

3. **Scaling**
   - Stateless design allows horizontal scaling
   - Redis for production Channel Layer
   - PostgreSQL for production database

## Future Enhancements

1. **Real-time Updates**: Complete WebSocket implementation
2. **Payment Integration**: Venmo, PayPal, Zelle APIs
3. **Receipt History**: Optional email/phone registration
4. **Analytics**: Usage tracking and insights
5. **Multi-language**: i18n support