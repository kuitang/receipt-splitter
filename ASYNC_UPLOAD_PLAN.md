# Asynchronous Receipt Upload Implementation Plan

## Current State Analysis
- Upload is synchronous - OCR processing blocks the response
- After upload, redirects to edit page
- Blur is implemented using Tailwind CSS: `opacity-50 blur-sm`
- View page already has conditional rendering based on session

## Architectural Decision: Dynamic AJAX Approach

### Why Dynamic over Static Refresh:
1. **Consistency**: The view page already uses dynamic conditional rendering
2. **UX**: Smoother experience without page refresh
3. **Code Reuse**: Can leverage existing edit template structure
4. **Real-time**: Can show actual receipt structure while loading

### Implementation Approach
Use HTMX (already loaded) for progressive enhancement:
1. Upload creates receipt with "processing" status immediately
2. Returns edit page with blurred content and loading modal
3. Triggers async OCR processing
4. Polls for completion using HTMX
5. Dynamically updates content when ready

## Technical Implementation

### 1. Backend Changes

#### Models (`receipts/models.py`)
- Add `processing_status` field to Receipt:
  - `pending` - Just uploaded, awaiting OCR
  - `processing` - OCR in progress
  - `completed` - OCR done
  - `failed` - OCR failed

#### Views (`receipts/views.py`)
- Split `upload_receipt`:
  - Create receipt immediately with placeholder data
  - Start async OCR task
  - Return to edit page with loading state
- Add `check_processing_status` endpoint for polling
- Add `get_receipt_content` endpoint for HTMX partial

### 2. Frontend Changes

#### Edit Template (`templates/receipts/edit.html`)
- Add loading modal with spinner
- Blur content when `processing_status != 'completed'`
- Use HTMX polling to check status
- Replace content when ready

#### Loading Modal Design
```html
<div id="processing-modal">
  <div class="spinner"></div>
  <h2>Analyzing Your Receipt with AI ✨</h2>
  <p>Our AI is reading your receipt faster than a speed reader on espresso!</p>
  <p>Just a few more seconds...</p>
</div>
```

### 3. Async Processing

#### Using Django's Threading
- Simple approach using `threading.Thread`
- No need for Celery for this MVP
- Process OCR in background thread
- Update database when complete

## Implementation Steps

1. **Update Models**
   - Add processing_status field
   - Add migration

2. **Create Async OCR Handler**
   - Function to process OCR in thread
   - Update receipt when complete
   - Handle errors gracefully

3. **Update Upload View**
   - Create receipt immediately
   - Start async processing
   - Redirect to edit with loading state

4. **Create Status Check Endpoint**
   - Return JSON with processing status
   - Include partial HTML when complete

5. **Update Edit Template**
   - Add loading modal
   - Implement HTMX polling
   - Handle success/error states

6. **Add CSS Animations**
   - Spinner animation
   - Smooth transitions

## Testing Plan

1. **Unit Tests**
   - Test async processing logic
   - Test status transitions
   - Test error handling

2. **Integration Tests**
   - Upload and wait for processing
   - Test timeout scenarios
   - Test error recovery

3. **Manual Testing**
   - Test with various image sizes
   - Test network interruptions
   - Test multiple concurrent uploads

## Success Metrics
- Receipt appears immediately (< 500ms)
- Loading state is engaging
- OCR completes without blocking
- Smooth transition when ready
- Error states handled gracefully