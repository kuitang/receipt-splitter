#!/bin/bash
#
# Run integration tests for Receipt Splitter
# Usage:
#   ./run_tests.sh           # Run with mock OCR (default)
#   ./run_tests.sh --real    # Run with real OpenAI API
#   ./run_tests.sh --help    # Show help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default to mock OCR
USE_REAL_OCR=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --real)
            USE_REAL_OCR=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --real    Use real OpenAI API instead of mock data"
            echo "  --help    Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  INTEGRATION_TEST_REAL_OPENAI_OCR=true  # Same as --real flag"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Check if Django server is running
if ! curl -s http://localhost:8000 > /dev/null 2>&1; then
    echo -e "${RED}❌ Django server is not running!${NC}"
    echo "Please start the server first:"
    echo "  cd .. && python manage.py runserver"
    exit 1
fi

echo -e "${GREEN}✅ Django server is running${NC}"

# Set environment variable for OCR
if [ "$USE_REAL_OCR" = true ]; then
    export INTEGRATION_TEST_REAL_OPENAI_OCR=true
    echo -e "${YELLOW}⚠️  Using REAL OpenAI API (this will cost money!)${NC}"
else
    export INTEGRATION_TEST_REAL_OPENAI_OCR=false
    echo -e "${GREEN}✅ Using mock OCR data (no API calls)${NC}"
fi

# Activate virtual environment if it exists
if [ -f "../venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source ../venv/bin/activate
fi

# Run the test suite
echo ""
echo "Running integration tests..."
echo "============================"
python test_suite.py

# Capture exit code
EXIT_CODE=$?

# Show result
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All integration tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed!${NC}"
fi

exit $EXIT_CODE