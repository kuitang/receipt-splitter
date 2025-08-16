# Integration Test Suite

Consolidated integration tests for the Receipt Splitter application with OCR mocking support.

## Quick Start

```bash
# Run with mock OCR (default - no API costs)
./integration_test/run_tests.sh

# Run with real OpenAI API (costs money!)
./integration_test/run_tests.sh --real

# Or use environment variable
INTEGRATION_TEST_REAL_OPENAI_OCR=true python integration_test/test_suite.py
```

## Test Architecture

### OCR Mocking System
- **Environment Variable**: `INTEGRATION_TEST_REAL_OPENAI_OCR`
- **Default**: `false` (uses mock data)
- **Mock Data**: Provides consistent test data without API calls
- **Real Mode**: Uses actual OpenAI Vision API when explicitly enabled

### Test Principles
1. **No Direct Imports**: Tests interact only via HTTP API
2. **Session Isolation**: Each test creates fresh sessions
3. **Data Cleanup**: Automatic cleanup after test runs
4. **Clear Logging**: Shows whether using mock or real OCR

## Test Coverage

### 1. Complete Workflow Test
End-to-end test of the entire receipt lifecycle:
- Upload receipt with OCR processing
- Edit with invalid data (validation check)
- Save valid data
- Attempt to finalize unbalanced receipt (should fail)
- Finalize balanced receipt
- Multiple users claim items
- Verify totals and calculations
- Test unclaim functionality

### 2. Security Tests
Based on SECURITY_AUDIT_REPORT.md findings:

#### Input Validation
- XSS prevention in text fields
- SQL injection prevention
- Input sanitization

#### File Upload Security
- File size limits (max 10MB)
- Empty file rejection
- Malicious file handling

#### Session Security
- Session isolation between users
- Unauthorized edit prevention
- Access control validation

### 3. Validation Tests
- Balanced receipt validation
- Unbalanced receipt detection
- Negative tip (discount) handling
- Item total calculations

### 4. Performance Tests
- Large receipt handling (50+ items)
- Update performance
- Claim performance
- Data integrity at scale

## Mock Data Scenarios

The mock system provides different data based on input:

| Image Size | Mock Scenario | Description |
|------------|---------------|-------------|
| < 100 bytes | Minimal | Single item receipt |
| < 1000 bytes | Default | 3 items, balanced |
| < 5000 bytes | Unbalanced | Validation testing |
| >= 5000 bytes | Large | 20+ items |

## File Structure

```
integration_test/
├── README.md           # This file
├── run_tests.sh        # Main test runner script
├── test_suite.py       # Consolidated test suite
├── base_test.py        # Base classes and utilities
├── mock_ocr.py         # OCR mocking system
└── (legacy tests)      # To be removed
```

## Running Individual Tests

```python
# Run specific test class
from integration_test.test_suite import ReceiptWorkflowTest
test = ReceiptWorkflowTest()
test.test_complete_workflow()

# Run security tests only
from integration_test.test_suite import SecurityValidationTest
test = SecurityValidationTest()
test.test_input_validation()
test.test_file_upload_security()
test.test_session_security()
```

## Test Output Example

```
🧪 RECEIPT SPLITTER INTEGRATION TEST SUITE
==================================================

📋 OCR Configuration:
   Status: Using Mock OCR Data
   Environment Variable: INTEGRATION_TEST_REAL_OPENAI_OCR=false

🧪 Complete Receipt Workflow Test
==================================================
📤 Step 1: Upload Receipt
   ✓ Receipt uploaded, slug: abc123
⏳ Step 2: Wait for Processing
   ✓ Receipt processed successfully
📊 Step 3: Verify OCR Data
   ✓ OCR extracted 3 items
   ✓ Restaurant: Test Restaurant
...

TEST SUMMARY
==================================================
  ✅ Complete Workflow
  ✅ Input Validation Security
  ✅ File Upload Security
  ✅ Session Security
  ✅ Balance Validation
  ✅ Large Receipt Performance
----------------------------------------------
Results: 6/6 passed
✅ ALL TESTS PASSED
```

## Development

### Adding New Tests

1. Create test class extending `IntegrationTestBase`
2. Use provided helper methods for API interactions
3. Follow naming convention: `test_*` for test methods
4. Add to `run_all_tests()` in test_suite.py

### Mock Data Customization

Edit `mock_ocr.py` to add new mock scenarios:

```python
@staticmethod
def get_custom_receipt():
    return {
        "restaurant_name": "Custom Restaurant",
        "items": [...],
        # ... your mock data
    }
```

## Requirements

- Django server running on localhost:8000
- Python virtual environment activated
- For real OCR: OpenAI API key in settings

## Troubleshooting

### Server Not Running
```
❌ Django server is not running!
Please start the server first:
  cd .. && python manage.py runserver
```

### Virtual Environment Issues
```bash
# Activate virtual environment manually
source venv/bin/activate
```

### OCR Mock Not Working
Check environment variable:
```bash
echo $INTEGRATION_TEST_REAL_OPENAI_OCR
# Should output: false (or empty)
```

## Legacy Tests (To Be Removed)

The following files are superseded by the consolidated suite:
- test_ocr_integration.py
- test_django_integration.py
- test_async_upload.py
- test_balance_validation.py
- Individual test_*.py files in parent directory

These will be removed after confirming the consolidated suite covers all scenarios.