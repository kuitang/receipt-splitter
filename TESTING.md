# Testing Commands

## Prerequisites

Before running any tests, ensure the environment is properly set up:

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Set required environment variables
export SECRET_KEY='test-key-for-testing-only'

# 3. Collect static files (required for integration tests)
python manage.py collectstatic --noinput
```

## JavaScript Tests
```bash
npm test
```

## Django Unit Tests
```bash
source venv/bin/activate
export SECRET_KEY='test-key-for-testing-only'
python manage.py test
```

## Security Tests
```bash
source venv/bin/activate
export SECRET_KEY='test-key-for-testing-only'
python manage.py test receipts.test_javascript_security -v 2
```

## Integration Tests
# Run all tests
python integration_test/test_suite.py

# Run specific test classes
python integration_test/test_suite.py ValidationTest SecurityValidationTest

# List available classes
python integration_test/test_suite.py --list

# Legacy commands
```bash
source venv/bin/activate
export SECRET_KEY='test-key-for-testing-only'
cd integration_test && ./run_tests.sh
```

**Note**: Integration tests automatically set `DEBUG=true` to avoid static file hashing issues.

## OCR Unit Tests
```bash
source venv/bin/activate
export SECRET_KEY='test-key-for-testing-only'
python -m unittest discover lib.ocr.tests -v
```

## Test Results Summary

### JavaScript Tests ✅
- **Status**: All 58 tests passing
- **Coverage**: DOM manipulation, validation, race conditions, floating-point precision

### Integration Tests ✅  
- **Status**: 9/13 tests passing (significant improvement with DEBUG=true fix)
- **Working**: Core workflow, permissions, security validation, UI consistency, responsive images, image links
- **Issues**: Only rate limiting (429 errors) causes remaining test failures

### Django Unit Tests 🟡
- **Status**: Mixed results with some environment-specific failures
- **Core functionality**: Working correctly
- **Issues**: Some test environment configuration dependencies

## Known Issues

1. **Rate Limiting**: Integration tests may hit rate limits in rapid succession  
2. **Timezone Warnings**: DateTimeField warnings in test environment (not production issue)

## JavaScript Template System Testing

When running JavaScript tests with the new template-based system, the tests need access to the Django-rendered HTML templates. To eliminate duplication, templates are automatically generated from Django before tests run.

### Automatic Template Generation

Templates are generated from Django using a management command:

```bash
# Manually generate templates
python manage.py generate_test_templates

# Or use npm (automatically runs before tests)
npm run generate-templates
```

This generates:
- `test/js/generated-templates.js` - JavaScript module with templates
- `test/js/test-templates.html` - HTML reference file

### Test Setup

Tests import and use the generated templates:

```javascript
import { testTemplates, setupTestTemplates } from './generated-templates.js';

beforeEach(() => {
    document.body.innerHTML = `
        <!-- Regular test DOM elements -->
        <div id="items-container"></div>
    `;
    
    // Add Django-generated templates to DOM
    setupTestTemplates(document);
});
```

### Template Requirements

The following templates are included in the generated file:
- `item-row-template`: Required for `addItem()` function in edit-page.js
- `claim-input-template`: Required for claim input generation in view-page.js  
- `participant-entry-template`: Required for participant display functions
- `claims-display-template`: Required for claims display functions
- `polling-error-template`: Required for error banner display

### Important Notes

1. **DO NOT EDIT** `generated-templates.js` manually - it's auto-generated
2. Templates are automatically regenerated before tests run (`npm test`)
3. If templates change in Django, they'll be automatically updated in tests
4. This ensures tests always use the actual Django templates (single source of truth)
