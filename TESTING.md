# Testing Documentation

## JavaScript Unit Tests

The receipt editor includes comprehensive JavaScript unit tests covering all functionality.

### Running Tests

#### 1. Node.js Tests (Recommended)
```bash
# Install dependencies (first time only)
npm install

# Run all tests
npm test

# Watch mode (auto-runs on file changes) - requires nodemon
npm run test:watch
```

Expected output:
```
Loading receipt-editor.js...
Running tests...

🧪 Running Receipt Editor Unit Tests
==================================================

📋 Basic Functionality Tests
  ✅ should have all functions available
  ✅ should calculate subtotal correctly
  ✅ should update subtotal field

📋 Item Removal Tests
  ✅ should remove item and update subtotal

... more tests ...

==================================================
Test Results: 8 passed, 0 failed
==================================================
```

#### 2. Browser Tests

Open the test runner in your browser:
```bash
npm run test:browser
# Then open: http://localhost:8000/static/run_tests.html
```

**What you'll see in run_tests.html:**

1. **Initial Screen**: Shows "Click 'Run All Tests' to begin testing..."
2. **Click "Run All Tests" button**: The tests will execute
3. **Test Output**: You'll see colored output showing:
   - 📋 Test group names in blue
   - ✅ Passed tests in green  
   - ❌ Failed tests in red (if any)
   - Detailed error messages for failures
4. **Summary Box**: After tests complete, a summary box appears showing:
   - Total number of tests
   - Number passed (green)
   - Number failed (red)
   - Overall status message

The page has a dark theme similar to VS Code for easy reading.

### Test Coverage

The test suite covers:

#### Core Functionality
- Subtotal calculation from line items
- Subtotal updates when items are removed
- Item total calculations with full precision
- Empty items list handling

#### UI Behavior
- Warning banner visibility based on balance status
- Finalize button enable/disable based on validation
- Real-time validation feedback

#### Validation
- Detection of unbalanced receipts
- Validation of balanced receipts
- Negative subtotal prevention
- Negative tax/tip support (for discounts)

#### Item Management
- Adding new items with correct structure
- Event listener attachment to new items
- Multiple item deletions in sequence
- Proration recalculation after removal

#### Global Availability
- All functions exposed globally in browser
- receiptIsBalanced state management
- attachItemListeners functionality

#### Integration Tests
- Complex multi-step scenarios
- Balance maintenance through operations
- Validation updates with changes

### Test Files

- `static/js/receipt-editor.test.js` - Full test suite (browser-compatible)
- `static/js/receipt-editor-node-test.js` - Node.js test runner with jsdom
- `static/run_tests.html` - Browser-based test runner UI

### Adding New Tests

To add new tests, edit `static/js/receipt-editor.test.js`:

```javascript
TestRunner.describe('My New Test Group', () => {
    TestRunner.it('should do something specific', () => {
        setupDOM();
        // Your test code here
        TestRunner.assertEqual(actual, expected);
    });
});
```

### Continuous Testing

During development, use watch mode to automatically run tests when files change:
```bash
npm run test:watch
```

This requires installing nodemon globally:
```bash
npm install -g nodemon
```

## Test Organization

### Library Structure
```
lib/
└── ocr/
    ├── __init__.py
    ├── ocr_lib.py         # Main OCR library
    └── tests/
        ├── __init__.py
        ├── test_ocr_lib.py        # OCR library unit tests
        ├── test_ocr_correction.py # Total correction tests
        ├── test_ocr_unit.py       # Additional unit tests
        └── test_ocr_cache.py      # Cache functionality tests
```

### Integration Tests
```
integration_test/
├── test_suite.py          # Complete consolidated test suite
├── base_test.py           # Base test classes and utilities
├── mock_ocr.py            # OCR mocking system
├── run_tests.sh           # Test runner script
└── README.md              # Integration test documentation
```

## Running Tests

### OCR Unit Tests
```bash
# Run all OCR unit tests
source venv/bin/activate
python -m unittest discover lib.ocr.tests -v

# Run specific test module
python -m unittest lib.ocr.tests.test_ocr_correction -v
```

### Integration Tests
```bash
# Run with mock OCR (default - no API costs)
./integration_test/run_tests.sh

# Run with real OpenAI API (costs money!)
./integration_test/run_tests.sh --real

# Or directly with Python
export INTEGRATION_TEST_REAL_OPENAI_OCR=false
python integration_test/test_suite.py
```

### Test Coverage
The consolidated integration test suite covers:
- ✅ **Complete Workflow**: Upload → edit → finalize → claim lifecycle
- ✅ **Input Validation Security**: XSS prevention, SQL injection prevention
- ✅ **File Upload Security**: Size limits, malicious file rejection, MIME spoofing prevention
- ✅ **Enhanced Security Validation**: python-magic integration, shell script blocking
- ✅ **Rate Limiting**: Upload burst testing with actual rate calculation
- ✅ **Balance Validation**: Receipt balance verification, negative tip support
- ✅ **Frontend HEIC Support**: HTML accept attributes, MIME type validation
- ✅ **UI Design Consistency**: Page loading, CSS framework usage
- ✅ **Large Receipt Performance**: 50+ items, update/claim performance
- ✅ **Session Security**: Isolation, unauthorized access prevention, concurrent edits

### OCR Mocking
Tests use mock OCR data by default to avoid API costs. Control with environment variable:
- `INTEGRATION_TEST_REAL_OPENAI_OCR=false` - Use mock data (default)
- `INTEGRATION_TEST_REAL_OPENAI_OCR=true` - Use real OpenAI API (costs money!)

Mock data provides different scenarios based on image size:
- < 100 bytes: Minimal receipt (1 item)
- < 1000 bytes: Default receipt (3 items, balanced)
- < 5000 bytes: Unbalanced receipt (for validation testing)
- ≥ 5000 bytes: Large receipt (20+ items)

### Django Unit Tests
```bash
source venv/bin/activate
python manage.py test
```

### Security Dependencies
The test suite now requires these security dependencies:
- `python-magic==0.4.27` - For proper file type detection
- `bleach==6.2.0` - For HTML sanitization
- `pillow-heif==1.1.0` - For HEIC/HEIF image support

These are automatically installed via `requirements.txt`.

## Manual Testing Checklist

When testing the receipt editor manually:

- [ ] Upload a receipt image
- [ ] Verify OCR extracts data correctly
- [ ] Add a new line item
- [ ] Delete a line item - verify subtotal updates
- [ ] Edit item quantities and prices
- [ ] Verify prorations update correctly
- [ ] Try to finalize with unbalanced receipt - should show warning
- [ ] Balance the receipt - warning should disappear
- [ ] Finalize balanced receipt successfully
- [ ] Test negative tax/tip for discounts
- [ ] Share link works correctly