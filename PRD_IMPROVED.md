# Communist Style: Smart Receipt Splitter
**Version 2.0 - Production Ready Specification**

## Executive Summary
"Communist Style" is an ironically titled web application that enables groups to split bills based on actual consumption rather than equally (hence the ironic communist reference). The app uses OCR technology to digitize receipts and provides a frictionless, account-free experience for splitting expenses among friends.

## Technology Stack
- **Backend**: Django (multi-page webapp for reliable testing and progressive enhancement)
- **Database**: SQLite (development) / PostgreSQL (production)
- **Frontend**: HTMX + Tailwind CSS (mobile-first, progressive enhancement)
- **OCR Service**: OpenAI Vision API for receipt parsing
- **Image Generation**: OpenAI DALL-E for sample images
- **Real-time Updates**: Django Channels with WebSockets
- **Hosting**: Scalable cloud deployment (Railway/Fly.io recommended)
- **Testing**: Django test framework + curl for endpoint validation

## Core Features & User Flows

### 1. Landing Page
**Purpose**: Convert visitors to users with clear value proposition

**Requirements**:
- Hero section with app title and tagline
- 3-4 illustrative sample images showing conventionally attractive friend groups
- Clear "Upload Receipt" CTA button
- Brief explanation of how it works (3 steps max)
- Mobile-optimized responsive design
- Fast load time (<2 seconds)

### 2. Uploader Flow

#### 2.1 Receipt Upload & Processing
**User Action**: Upload receipt image via camera or file selection

**Technical Requirements**:
- Accept image formats: JPEG, PNG, HEIF (iOS), WebP
- Max file size: 10MB
- Image preprocessing: Auto-rotate, enhance contrast
- Show loading animation during OCR processing

**OCR Processing**:
```python
# Structured data extraction
{
    "restaurant_name": str,
    "date": datetime,
    "items": [
        {
            "name": str,
            "quantity": int,
            "unit_price": Decimal,
            "total_price": Decimal
        }
    ],
    "subtotal": Decimal,
    "tax": Decimal,
    "tip": Decimal,
    "total": Decimal
}
```

**Validation Rules**:
- Sum of items must equal subtotal (±$0.01 tolerance)
- Subtotal + tax + tip must equal total (±$0.01 tolerance)
- All monetary values use Decimal type for precision

**Error Handling**:
- OCR failure: Offer manual entry form
- Validation failure: Highlight discrepancies, allow manual correction
- Poor image quality: Request re-upload with tips

#### 2.2 User Identification
**Requirements**:
- Request uploader's name (required, 2-50 characters)
- Validate against profanity filter
- Store in session for future reference

#### 2.3 Receipt Editing Interface
**Display Requirements**:
- Editable table with all line items
- Show quantity, unit price, total for each item
- Display prorated tax/tip per item with tooltip explanation

**Proration Formula**:
```
item_tax = (item_total / subtotal) * total_tax
item_tip = (item_total / subtotal) * total_tip
item_share = item_total + item_tax + item_tip
```

**Editing Features**:
- Edit item names (autocomplete from common items)
- Adjust quantities with +/- buttons
- Modify prices with validation
- Add/remove items
- Real-time total recalculation
- Undo/redo functionality (last 10 actions)

#### 2.4 Save & Share
**Save Confirmation**:
- Modal: "Once saved, this receipt cannot be edited. Continue?"
- Show final totals for verification
- Require explicit confirmation

**URL Generation**:
- Format: `domain.com/r/{uuid}` (use UUID4 for security)
- Provide copy button with success feedback
- Generate QR code for easy mobile sharing
- Show share options (SMS, WhatsApp, email)

### 3. Invitee Flow

#### 3.1 Initial Access
**Security & Identification**:
- Blur receipt content initially
- Require name entry (validated for uniqueness)
- Check for existing session cookie
- Prevent name collisions with smart suggestions

**Name Collision Handling**:
```python
if name_exists:
    suggestions = [
        f"{name} 2",
        f"{name} ({first_letter_last_name})",
        f"{name}_{random_suffix}"
    ]
    return suggestions
```

#### 3.2 Receipt Interaction
**Display Features**:
- Show onboarding modal (dismissible, show once per session)
- Display all items with claim status
- Real-time updates when others claim items
- Show who's currently viewing (presence indicators)

**Item Claiming UI**:
- Unclaimed: Checkbox or "Claim" button
- Claimed by others: Show name, grayed out
- Multiple quantity: Number spinner (0 to max available)
- Running total in sticky footer/header

**Real-time Updates**:
- WebSocket connection for live updates
- Show animation when items are claimed
- Update available quantities instantly
- Display notification for new viewers

#### 3.3 Claim Confirmation
**Confirmation Flow**:
- Show detailed breakdown: items + tax + tip = total
- Warning: "You're committing to pay $X.XX"
- 30-second grace period for undo
- Success message with payment suggestions

### 4. Payment Integration (Future Feature)
**Options**:
- Generate Venmo/PayPal/Zelle links
- Show uploader's payment details
- Export to expense tracking apps
- Email receipt summary

## Data Models

### Receipt Model
```python
class Receipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    uploader_name = models.CharField(max_length=50)
    restaurant_name = models.CharField(max_length=100)
    date = models.DateTimeField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    tip = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField()
    is_finalized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # 30 days from creation
```

### LineItem Model
```python
class LineItem(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    prorated_tax = models.DecimalField(max_digits=10, decimal_places=2)
    prorated_tip = models.DecimalField(max_digits=10, decimal_places=2)
```

### Claim Model
```python
class Claim(models.Model):
    line_item = models.ForeignKey(LineItem, on_delete=models.CASCADE)
    claimer_name = models.CharField(max_length=50)
    quantity_claimed = models.IntegerField(default=1)
    session_id = models.CharField(max_length=100)
    claimed_at = models.DateTimeField(auto_now_add=True)
    grace_period_ends = models.DateTimeField()  # 30 seconds after claim
```

## API Endpoints

### Core Endpoints
```
POST   /api/upload-receipt/     # Upload and process receipt
GET    /api/receipt/{uuid}/     # Get receipt details
PUT    /api/receipt/{uuid}/     # Update receipt (pre-finalization)
POST   /api/receipt/{uuid}/finalize/  # Finalize receipt

POST   /api/claim/              # Claim items
DELETE /api/claim/{id}/         # Undo claim (within grace period)
GET    /api/receipt/{uuid}/claims/  # Get all claims (WebSocket preferred)

POST   /api/validate-name/      # Check name availability
GET    /api/receipt/{uuid}/viewers/  # Get active viewers
```

## Security & Privacy

### Security Measures
1. **URL Security**: Use UUID4 (cryptographically random)
2. **Session Management**: 
   - HttpOnly, Secure, SameSite cookies
   - Device fingerprinting for additional validation
3. **Rate Limiting**:
   - OCR: 10 requests per IP per minute
   - API: 100 requests per IP per minute
4. **Input Validation**: 
   - Sanitize all user inputs
   - SQL injection prevention via ORM
   - XSS protection via template escaping

### Privacy Protection
1. **PII Handling**:
   - Redact credit card numbers from images
   - No email/phone collection required
   - Names are receipt-scoped only
2. **Data Retention**:
   - Receipts expire after 30 days
   - Automatic deletion of expired data
   - No long-term user tracking
3. **GDPR Compliance**:
   - Right to deletion via support
   - Minimal data collection
   - Clear privacy policy

## Mobile Optimization

### iOS Safari Specific
- Handle viewport-fit for notched devices
- Prevent zoom on input focus
- Support for touch-action gestures
- PWA capabilities with app manifest
- Handle iOS image orientation EXIF data

### Performance Requirements
- Initial load: <2 seconds on 3G
- Time to interactive: <3 seconds
- Lighthouse score: >90
- Offline support for claimed items view

## Error Handling & Edge Cases

### OCR Edge Cases
- Multiple receipts: Process first, warn user
- Foreign languages: Support common restaurant terms
- Handwritten additions: Flag for manual review
- Damaged receipts: Enhance image, fallback to manual

### Calculation Edge Cases
- Items with modifiers: Treat as single item
- Discounts: Apply proportionally to items
- Multiple tax rates: Use weighted average
- Service charges: Treat as additional tip
- Split items on original: Warn and adjust

### User Experience Edge Cases
- Network interruption: Queue claims, sync when connected
- Simultaneous claims: First-come-first-served with notifications
- Grace period conflicts: Last action wins
- Browser back button: Maintain state properly

## Testing Requirements

### Unit Tests
- Proration calculations accuracy
- URL generation uniqueness
- Session management security
- Claim validation logic

### Integration Tests
- OCR pipeline end-to-end
- WebSocket real-time updates
- Payment link generation
- Data expiration jobs

### User Acceptance Tests
- Complete uploader flow
- Complete invitee flow
- Multi-user simultaneous claims
- Mobile device compatibility

## Success Metrics

### Technical Metrics
- OCR accuracy: >95% for clear receipts
- Page load time: <2 seconds (p95)
- Uptime: 99.9%
- Zero data breaches

### User Metrics
- Upload to share: <2 minutes average
- Claim completion rate: >80%
- User errors: <5% of sessions
- Mobile usage: >60%

## MVP vs Future Features

### MVP (Version 1.0)
- Receipt upload and OCR
- Manual editing capability
- Basic claiming functionality
- Mobile-responsive design
- 30-day data retention

### Future Enhancements (Version 2.0+)
- Payment platform integration
- Receipt history via email/phone
- Group expense tracking
- Recurring split templates
- Multi-language support
- Export to expense apps
- Social features (comments, reactions)
- Analytics dashboard for groups

## Implementation Notes for Claude

### Development Approach
1. Start with Django project setup and models
2. Implement receipt upload and OCR integration
3. Build editing interface with HTMX
4. Add claiming functionality
5. Implement WebSocket real-time updates
6. Add mobile optimizations
7. Complete security measures
8. Deploy with monitoring

### Testing Strategy
- Write tests alongside features
- Use Django TestCase for models
- Mock external APIs (OpenAI)
- Test with curl for HTTP endpoints
- Validate with multiple browsers/devices

### Commit Strategy
- Commit after each working feature
- Include test evidence in commit messages
- Maintain clean .gitignore
- Document architectural decisions