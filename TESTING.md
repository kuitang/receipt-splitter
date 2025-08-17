# Testing Commands

## JavaScript Tests
```bash
npm test
```

## Django Tests
```bash
source venv/bin/activate
python manage.py test
```

## Security Tests
```bash
source venv/bin/activate
python manage.py test receipts.test_javascript_security -v 2
```

## Integration Tests
```bash
source venv/bin/activate
# Run all tests
python integration_test/test_suite.py

# Run specific test classes
python integration_test/test_suite.py ValidationTest SecurityValidationTest

# List available classes
python integration_test/test_suite.py --list
```

## OCR Unit Tests
```bash
source venv/bin/activate
python -m unittest discover lib.ocr.tests -v
```