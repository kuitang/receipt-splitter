#!/bin/bash
#
# Run integration tests for Receipt Splitter.
# Usage:
#   ./run_tests.sh            # Run with mocked OCR (default)
#   ./run_tests.sh --real     # Run with the real OpenAI OCR pipeline
#   ./run_tests.sh --help     # Show help

set -euo pipefail

USE_REAL_OCR=false

for arg in "$@"; do
    case "$arg" in
        --real)
            USE_REAL_OCR=true
            shift
            ;;
        --help)
            cat <<USAGE
Usage: $0 [--real]

Options:
  --real    Run the suite against the real OpenAI OCR service.
            Requires valid API credentials in the environment.
  --help    Show this message.
USAGE
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 1
            ;;
    esac
done

cd "$(dirname "$0")/.."

if [ "$USE_REAL_OCR" = true ]; then
    export INTEGRATION_TEST_REAL_OPENAI_OCR=true
    echo "⚠️  Using REAL OpenAI OCR (costs money)."
else
    export INTEGRATION_TEST_REAL_OPENAI_OCR=false
    echo "✅ Using mock OCR data."
fi

env | grep INTEGRATION_TEST_REAL_OPENAI_OCR

pytest -m integration
