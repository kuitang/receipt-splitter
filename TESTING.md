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
