# Test Suites

The project test harness is organised into three independent suites so they can run in
parallel in CI or locally. All Python tests use **pytest** with `pytest-django` and share
the same configuration defined in `pytest.ini`.

## Prerequisites

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
npm install
```

Environment variables are automatically populated for the test runner (`SECRET_KEY`,
`DJANGO_SETTINGS_MODULE`, `USE_ASYNC_PROCESSING`) so no additional exports are required.
If you prefer to supply your own values, set them before invoking the commands below.

## 1. Backend Unit Tests

Covers Django models, services, validators and the OCR helper modules. Uses an
in-memory SQLite database managed by `pytest-django`.

```bash
pytest -m backend
```

### Notes
- Runs all tests in `receipts/` and `lib/ocr/tests/`.
- Requires the `libmagic` system library in production; the pytest harness stubs
  MIME detection when the shared object is not present so local runs remain
  reliable.
- Database is created/destroyed automatically; no need to run migrations manually.

## 2. Integration Tests

Exercises pytest-native scenarios in `integration_test/test_*.py`. Each module
focuses on a cohesive area (workflow, claims, UI) so failures surface quickly
without paging through ad-hoc console output.

```bash
pytest -m integration
```

### Notes
- Uses the mocked OCR pipeline by default; set
  `INTEGRATION_TEST_REAL_OPENAI_OCR=true` to hit the real API.
- Creates and finalises receipts via Django's test client, so no development
  server is required.
- Safe to run in parallel with the backend suite because each test initialises its
  own database transaction.

## 3. Frontend (Vitest) Suite

JavaScript unit tests run headless via Vitest. Test HTML templates are generated before
Vitest executes so no manual Django setup is required.

```bash
npm test -- --run
```

### Notes
- The `pretest` hook calls `python3 scripts/generate_test_templates.py` which injects
  the required environment variables automatically.
- Messages such as `Error: Not implemented: navigation` come from JSDOM and can be
  ignored as long as Vitest reports all tests passing.

## Running Everything Sequentially

```bash
pytest -m backend
pytest -m integration
npm test -- --run
```

## Parallel Execution

The suites do not share state. You can run them in parallel processes (or CI jobs)
as long as each process installs dependencies and creates its own virtual environment.

## Manual Checks

The `manual_tests/` directory contains exploratory scripts that are intentionally
excluded from automated runs. For example:

```bash
python manual_tests/rate_limiting_check.py
```

This script requires a locally running development server and is useful for spot
checking rate-limiting behaviour.

## Troubleshooting

- **Missing libmagic** – Install the `libmagic` system package (`libmagic1` on
  Debian/Ubuntu). Tests provide a signature-based stub when the shared object is
  unavailable, but the production build expects the real library.
- **Vitest template errors** – Ensure `python3` is on your `PATH`; the helper script
  uses it to call `manage.py generate_test_templates`.
