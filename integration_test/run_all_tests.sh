#!/bin/bash
# Run all integration tests

echo "=========================================="
echo "RUNNING ALL INTEGRATION TESTS"
echo "=========================================="

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Change to project root
cd "$(dirname "$0")/.."

# Run OCR integration tests
echo ""
echo "🧪 Running OCR Integration Tests..."
python integration_test/test_ocr_integration.py
OCR_RESULT=$?

# Run Django integration tests
echo ""
echo "🧪 Running Django Integration Tests..."
python integration_test/test_django_integration.py
DJANGO_RESULT=$?

# Summary
echo ""
echo "=========================================="
echo "INTEGRATION TEST RESULTS"
echo "=========================================="

if [ $OCR_RESULT -eq 0 ]; then
    echo "✅ OCR Integration Tests: PASSED"
else
    echo "❌ OCR Integration Tests: FAILED"
fi

if [ $DJANGO_RESULT -eq 0 ]; then
    echo "✅ Django Integration Tests: PASSED"
else
    echo "❌ Django Integration Tests: FAILED"
fi

echo "=========================================="

# Exit with failure if any test failed
if [ $OCR_RESULT -ne 0 ] || [ $DJANGO_RESULT -ne 0 ]; then
    exit 1
fi

exit 0