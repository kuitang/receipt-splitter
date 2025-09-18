# Legacy Tests to Remove

These test files have been superseded by the pytest-based integration suite in
`integration_test/test_*.py`.

## Files to Remove After Verification

### In Root Directory
- `test_ocr.py` - Basic OCR testing, covered by workflow test
- `test_ocr_unit.py` - Unit tests, some covered by integration tests
- `test_ocr_correction.py` - Correction logic, covered by validation tests
- `test_ocr_cache.py` - Cache testing, not critical for integration
- `test_fix.py` - Temporary fix testing
- `test_cache_fix.py` - Cache fix testing
- `test_web_cache.py` - Web cache testing

### In integration_test Directory
- `test_async_upload.py` - Covered by workflow test
- `test_balance_validation.py` - Covered by validation tests
- `test_clipboard_ui.py` - UI specific, keep if needed
- `test_design_consistency.py` - UI specific, keep if needed
- `test_django_integration.py` - Fully covered by new suite
- `test_e2e_balance.py` - Covered by workflow and validation tests
- `test_e2e_upload.py` - Covered by workflow test
- `test_frontend_heic.py` - Frontend specific, keep if needed
- `test_heic_async.py` - Covered by workflow test
- `test_heic_conversion.py` - Covered by mock OCR
- `test_image_formats.py` - Covered by mock OCR scenarios
- `test_ocr_cache_integration.py` - Cache specific, not critical
- `test_ocr_integration.py` - Fully covered by new suite
- `test_total_correction.py` - Covered by validation tests
- `test_ui_regression.py` - UI specific, keep if needed
- `run_all_tests.sh` - Replaced by new run_tests.sh

## Tests to Keep (UI/Frontend Specific)
- `test_clipboard_ui.py` - Tests clipboard functionality
- `test_design_consistency.py` - Tests design elements
- `test_frontend_heic.py` - Tests frontend HEIC support
- `test_ui_regression.py` - Tests UI regressions

## Verification Checklist

Before removing legacy tests, verify that the consolidated suite covers:

- [x] OCR processing (mock and real)
- [x] Receipt upload and async processing
- [x] Balance validation and correction
- [x] Complete workflow (upload, edit, finalize, claim)
- [x] Security validations (XSS, SQL injection, file upload)
- [x] Session isolation and access control
- [x] Performance with large receipts
- [x] Multiple user scenarios
- [x] Error handling and edge cases

## Migration Status

| Legacy Test | Covered By | Can Remove |
|-------------|------------|------------|
| test_ocr.py | workflow test | Yes |
| test_ocr_unit.py | validation tests | Yes |
| test_ocr_correction.py | validation tests | Yes |
| test_django_integration.py | complete suite | Yes |
| test_async_upload.py | workflow test | Yes |
| test_balance_validation.py | validation tests | Yes |
| test_e2e_*.py | workflow test | Yes |
| test_ocr_integration.py | complete suite | Yes |
| test_total_correction.py | validation tests | Yes |
| test_image_formats.py | mock scenarios | Yes |
| test_*cache*.py | Not critical | Yes |
| test_*ui*.py | UI specific | Keep |
| test_frontend_*.py | Frontend specific | Keep |

## Recommended Action

1. Run the consolidated test suite to ensure all tests pass
2. Keep UI/frontend specific tests that test browser behavior
3. Remove all other legacy tests listed above
4. Update TESTING.md to reference the new consolidated suite