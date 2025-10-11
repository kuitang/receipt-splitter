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

### Frontend Architecture

#### Template-Based JavaScript Pattern
The frontend uses a **server-rendered template abstraction** to avoid HTML duplication and improve testability:

1. **Django Templates as Source of Truth** (`templates/receipts/partials/js_templates.html`)
   - Reusable HTML components wrapped in `<template>` tags
   - Single source for both server-side rendering and client-side cloning
   - Components: item rows, claim inputs, participant entries, error banners

2. **Template Utilities** (`static/js/template-utils.js`)
   - `window.TemplateUtils` provides factory methods for creating DOM elements
   - Available methods: `createItemRow()`, `createClaimInput()`, `createParticipantEntry()`, etc.
   - Handles template cloning and data binding

3. **Test Template Generation**
   - Command: `npm run generate-templates` (or `python3 manage.py generate_test_templates`)
   - Renders Django templates to `test/js/generated-templates.js`
   - Enables JSDOM testing with real HTML structures

#### When to Use Templates vs. Manual DOM
- ✅ **Use `TemplateUtils` for**: Reusable components, complex HTML structures, user-visible content
- ✅ **Create new templates when**: Adding new UI patterns, repeating HTML across files
- ❌ **Avoid**: String concatenation with `innerHTML`, duplicating HTML in templates and JS
- ✅ **Manual DOM is OK for**: Simple wrappers, one-off elements, test fixtures

#### Template Workflow
```javascript
// 1. Add template to templates/receipts/partials/js_templates.html
<template id="my-widget-template">
  <div class="widget" data-widget-id="">
    <span data-widget-name></span>
  </div>
</template>

// 2. Add factory method to static/js/template-utils.js
createMyWidget(id, name) {
    const clone = this.cloneTemplate('my-widget-template');
    if (!clone) return null;

    clone.querySelector('[data-widget-id]').dataset.widgetId = id;
    clone.querySelector('[data-widget-name]').textContent = name;
    return clone;
}

// 3. Regenerate test templates
// npm run generate-templates

// 4. Use in application code
const widget = window.TemplateUtils.createMyWidget('123', 'My Widget');
container.appendChild(widget);
```

### Testing Strategy

#### Backend Testing
- **Django unit tests**: Core business logic and models
- **Integration tests**: Full HTTP workflow with mock/real OCR
- Runtime logs stored in `run/` directory (excluded from git)

#### JavaScript Testing
- **Vitest test suite**: Frontend components and interactions in JSDOM environment
- **Template-based testing**: Tests use real Django-rendered HTML structures

**Test Setup Pattern:**
```javascript
import { setupTestEnvironment, setupTemplateUtils, setBodyHTML } from './test-setup.js';

// Initialize JSDOM and global mocks
setupTestEnvironment();

// Load template utilities
await setupTemplateUtils();

// In tests: setBodyHTML() auto-includes templates
beforeEach(() => {
    setBodyHTML('<div id="container"></div>');
    // Templates are automatically available via setupTestTemplates()
});
```

**Important:** After modifying Django templates, regenerate test templates:
```bash
npm run generate-templates
```

This ensures tests use the same HTML as production.

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

## JavaScript Best Practices

### Template Usage Guidelines

#### ✅ DO: Use TemplateUtils for Reusable Components
```javascript
// Good: Use template factory methods
const entry = window.TemplateUtils.createParticipantEntry(name, amount);
container.appendChild(entry);

const claimInput = window.TemplateUtils.createClaimInput(itemId, maxQty, currentVal);
section.appendChild(claimInput);
```

#### ❌ DON'T: String Concatenation for HTML
```javascript
// Bad: Inline HTML strings
div.innerHTML = `<span>${name}</span><span>$${amount}</span>`;

// Bad: Manual element creation for complex structures
const wrapper = document.createElement('div');
const nameSpan = document.createElement('span');
nameSpan.textContent = name;
wrapper.appendChild(nameSpan);
// ... (5+ lines for what a template does in 1)
```

#### When to Create a New Template

Create a new template in `js_templates.html` when:
- The HTML structure is reused in multiple places
- The component has 3+ elements or nested structure
- The component contains user data that needs XSS protection
- You find yourself copy-pasting HTML strings

**Don't create templates for:**
- Simple wrappers (`<div>`, `<span>`) with no children
- One-off UI elements used in a single function
- Test fixtures (use `setBodyHTML()` instead)

#### Security: Avoid XSS
```javascript
// ✅ Safe: Use textContent or templates with data attributes
element.textContent = userInput;
clone.querySelector('[data-name]').textContent = userInput;

// ❌ Dangerous: Direct innerHTML with user data
element.innerHTML = userInput; // XSS risk!
element.innerHTML = `<div>${userInput}</div>`; // Still dangerous!
```

### Module Organization

#### File Structure
- **Page-specific logic**: `edit-page.js`, `view-page.js`
- **Shared utilities**: `utils.js` (fetch, cookies, escaping)
- **Template management**: `template-utils.js`
- **Common UI patterns**: Use `common.js` if needed (currently unused)

#### Module Exports (for testing)
```javascript
// At end of file - export functions for unit tests
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        functionName,
        anotherFunction,
        _getState: () => ({ /* internal state */ }),
        _setState: (state) => { /* for test setup */ }
    };
}
```

### DOM Manipulation Patterns

#### Event Listeners
```javascript
// ✅ Good: Delegated events for dynamic content
container.addEventListener('click', (e) => {
    if (e.target.matches('[data-action="remove"]')) {
        handleRemove(e.target);
    }
});

// ✅ Good: Direct listeners for static elements
document.getElementById('save-button').addEventListener('click', save);

// ❌ Avoid: Inline event handlers
// Don't use: <button onclick="save()">
```

#### Data Attributes
```javascript
// ✅ Good: Use data attributes for IDs and metadata
const itemId = element.dataset.itemId;
const amount = parseFloat(element.dataset.amount);

// ✅ Good: Use data attributes for actions
button.dataset.action = 'confirm-claims';

// ❌ Avoid: Storing complex objects in data attributes
// Don't: element.dataset.config = JSON.stringify(obj);
```

### Performance Considerations

#### Minimize Reflows
```javascript
// ✅ Good: Batch DOM updates
const fragment = document.createDocumentFragment();
items.forEach(item => {
    const el = createItemElement(item);
    fragment.appendChild(el);
});
container.appendChild(fragment);

// ❌ Avoid: Multiple individual appends
items.forEach(item => {
    container.appendChild(createItemElement(item));
});
```

#### Debounce Input Events
```javascript
// ✅ Good: Use debouncing for expensive operations
let debounceTimer;
input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(expensiveCalculation, 300);
});
```