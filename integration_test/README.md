# Integration Test Suite

Pytest drives the integration scenarios using Django's test client and the helper
utilities in `base_test.py`. Each module focuses on a specific surface area so
failures point directly at the broken behaviour.

## Quick Start

```bash
# Run with the mocked OCR pipeline (default)
pytest -m integration

# Run via the convenience script
./integration_test/run_tests.sh

# Exercise the suite against the real OpenAI OCR API (costs money)
INTEGRATION_TEST_REAL_OPENAI_OCR=true pytest -m integration
```

## Test Modules

- `test_workflow.py` – upload, edit, finalise and claim a receipt end-to-end and
  enforce session ownership for edits.
- `test_claims.py` – verify the real-time claim API surfaces the latest data to
  concurrent users.
- `test_ui.py` – sanity-check rendered templates for HEIC support and responsive
  imagery hooks.

Common fixtures live in `conftest.py` and automatically patch the OCR layer to use
mocked data unless `INTEGRATION_TEST_REAL_OPENAI_OCR=true` is set.

## File Overview

```
integration_test/
├── base_test.py          # HTTP helpers and canned payloads
├── conftest.py           # Pytest fixtures and OCR patching
├── mock_ocr.py           # Mock OCR implementation
├── run_tests.sh          # Convenience wrapper for pytest
├── test_claims.py        # Claim-related scenarios
├── test_ui.py            # Template assertions
└── test_workflow.py      # End-to-end workflow coverage
```

## Tips

- The helpers create receipts entirely via HTTP calls, so no development server
  needs to be running.
- The mocked OCR layer derives scenarios from the uploaded image size; the
  default fixtures generate appropriately sized payloads.
- When using the real API, ensure `OPENAI_API_KEY` is exported and be prepared
  for billable requests.
