# Testing Commands

## Prerequisites

Before running any tests, ensure the environment is properly set up:

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Set required environment variables
export SECRET_KEY='test-key-for-testing-only'

# 3. Collect static files (required for integration tests)
python3 manage.py collectstatic --noinput
```

**Note**: Use `python3` instead of `python` as the python command may not be available in some environments.

## JavaScript Tests
```bash
npm test -- --run
```

**IMPORTANT**: Navigation errors in console output are JSDOM limitations, NOT test failures. If the test summary shows "X passed", all tests are successful.

## Django Unit Tests
```bash
source venv/bin/activate
export SECRET_KEY='test-key-for-testing-only'
python3 manage.py test
```

## Security Tests
```bash
source venv/bin/activate
export SECRET_KEY='test-key-for-testing-only'
python3 manage.py test receipts.test_javascript_security -v 2
```

## Integration Tests
```bash
source venv/bin/activate
export SECRET_KEY='test-key-for-testing-only'
python3 integration_test/test_suite.py
```

# Run specific test classes
```bash
python3 integration_test/test_suite.py ValidationTest SecurityValidationTest
```

# List available classes
```bash
python3 integration_test/test_suite.py --list
```

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
python3 -m unittest discover lib.ocr.tests -v
```

## Quick Test Commands for CI/Automation

For automated testing environments, run all tests with these commands:

```bash
# Prerequisites
source venv/bin/activate
export SECRET_KEY='test-key-for-testing-only'
python3 manage.py collectstatic --noinput

# Run all test suites
npm test -- --run                        # JavaScript (131 tests pass - ignore navigation errors)
python3 manage.py test                   # Django unit tests
python3 integration_test/test_suite.py   # Integration tests (all 20 pass)
python3 -m unittest discover lib.ocr.tests -v  # OCR unit tests
```

**IMPORTANT FOR AUTOMATED TESTING**: JavaScript tests show 'Error: Not implemented: navigation' messages in stderr, but these are JSDOM limitations, NOT test failures. If the test summary shows "X passed", all tests are successful.

## Expected Test Output

### Successful Test Runs

JavaScript tests (JSDOM navigation errors are normal):
```bash
 ✓ test/js/finalized-visibility.spec.js  (6 tests) 422ms
 ✓ test/js/view-page-essential.spec.js  (8 tests) 401ms
 ✓ test/js/edit-page.spec.js  (18 tests) 7459ms

 Test Files  9 passed (9)
      Tests  131 passed (131)
   Duration  10.13s
```

Django unit tests:
```bash
test_bug_scenario_same_session_different_names ... ok
test_participant_totals_grouped_by_name ... ok

----------------------------------------------------------------------
Ran 11 tests in 0.049s

OK
```

Integration tests:
```bash
  ✅ Balance Validation
  ✅ Security Validation
  ✅ UI Design Consistency
  ✅ Concurrent Claims - Basic Scenario
----------------------------------------------------------------------
Results: 20 passed, 0 failed, 0 skipped (20 total)
✅ ALL TESTS PASSED
```

OCR unit tests:
```bash
................
----------------------------------------------------------------------
Ran 18 tests in 1.324s

OK
```

### Notes
- **JSDOM Errors**: Lines like `Error: Not implemented: navigation` in JavaScript tests are JSDOM limitations, not actual failures
- **Success Indicators**: Look for "X passed (X)" counts and "OK" status rather than individual error messages
- **Debug Output**: OCR tests may show validation messages - these are informational, not failures

## Known Issues

1. **Python Command**: Use `python3` instead of `python` - the `python` command may not be available
2. **JavaScript Navigation Errors**: JSDOM shows navigation errors in stderr - these are NOT test failures, ignore them
3. **OCR Mock Integration**: Some OCR integration tests have complex mocking requirements 
4. **Timezone Warnings**: DateTimeField warnings in test environment (not production issue)

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
