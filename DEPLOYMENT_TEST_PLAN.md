# Deployment Test Plan

## Overview
This test plan ensures that the deployment-related changes work correctly with both SQLite (development) and PostgreSQL (production) configurations.

## Test Categories

### 1. Database Configuration Tests
**Purpose**: Verify that the app works with both SQLite and PostgreSQL configurations

#### Test 1.1: SQLite Configuration (Default)
- **Setup**: Default environment (no DATABASE_URL)
- **Expected**: App uses SQLite database
- **Commands**:
  ```bash
  unset DATABASE_URL
  python manage.py check --deploy
  python manage.py migrate
  python manage.py test
  ```

#### Test 1.2: PostgreSQL Configuration Simulation
- **Setup**: Mock PostgreSQL URL
- **Expected**: App configures for PostgreSQL
- **Commands**:
  ```bash
  export DATABASE_URL="postgres://user:pass@localhost:5432/testdb"
  python manage.py check --deploy
  # Note: Won't actually connect, but validates configuration
  ```

### 2. Static Files Tests
**Purpose**: Verify WhiteNoise static file handling works correctly

#### Test 2.1: Static File Collection
- **Commands**:
  ```bash
  python manage.py collectstatic --noinput
  ls -la staticfiles/
  ```
- **Expected**: Static files collected to staticfiles/ directory

#### Test 2.2: WhiteNoise Middleware
- **Setup**: Production-like settings
- **Commands**:
  ```bash
  export DEBUG="False"
  python manage.py check --deploy
  ```
- **Expected**: No warnings about static file serving

### 3. Security Configuration Tests
**Purpose**: Verify production security settings work correctly

#### Test 3.1: Production Security Check
- **Commands**:
  ```bash
  export DEBUG="False"
  export SECURE_SSL_REDIRECT="True"
  export SESSION_COOKIE_SECURE="True" 
  export CSRF_COOKIE_SECURE="True"
  export SECURE_HSTS="True"
  python manage.py check --deploy
  ```
- **Expected**: No security warnings

#### Test 3.2: CSRF Trusted Origins
- **Setup**: Test CSRF protection with Fly.io domains
- **Expected**: .fly.dev domains accepted

### 4. Integration Test Compatibility
**Purpose**: Ensure existing tests still pass with deployment changes

#### Test 4.1: Run Existing Test Suite
- **Commands**:
  ```bash
  export INTEGRATION_TEST_REAL_OPENAI_OCR=false
  pytest -m integration
  ```
- **Expected**: All tests pass

#### Test 4.2: Django Unit Tests
- **Commands**:
  ```bash
  python manage.py test
  ```
- **Expected**: All Django tests pass

#### Test 4.3: OCR Library Tests
- **Commands**:
  ```bash
  python -m unittest discover lib.ocr.tests -v
  ```
- **Expected**: All OCR tests pass

### 5. JavaScript Tests
**Purpose**: Verify frontend tests still work

#### Test 5.1: Node.js Tests
- **Commands**:
  ```bash
  npm test
  ```
- **Expected**: All JavaScript tests pass

### 6. Dependencies Tests
**Purpose**: Verify new dependencies don't break anything

#### Test 6.1: Import New Dependencies
- **Test Script**:
  ```python
  # Test that new dependencies can be imported
  import dj_database_url
  import whitenoise
  import psycopg2
  import gunicorn
  print("All deployment dependencies imported successfully")
  ```

#### Test 6.2: Multi-Stage Build Verification
- **Commands**:
  ```bash
  # Build multi-stage image
  DOCKER_BUILDKIT=1 docker build -t receipt-test .
  
  # Verify image size (should be ~150-180MB)
  docker images receipt-test
  
  # Test non-root user
  docker run --rm receipt-test whoami  # Should output: appuser
  ```

#### Test 6.3: Dependency Compatibility
- **Commands**:
  ```bash
  pip check
  ```
- **Expected**: No dependency conflicts

### 7. Configuration Validation Tests
**Purpose**: Test different environment configurations

#### Test 7.1: Development Configuration
- **Environment**: DEBUG=True, no DATABASE_URL
- **Expected**: SQLite database, debug mode enabled

#### Test 7.2: Production Configuration Simulation
- **Environment**: DEBUG=False, DATABASE_URL set, security flags enabled
- **Expected**: PostgreSQL config, security headers enabled

## Test Execution Order

1. **Prerequisites Check**
   ```bash
   pip install -r requirements.txt
   pip check
   ```

2. **Development Configuration Tests**
   ```bash
   unset DATABASE_URL
   export DEBUG="True"
   python manage.py check
   python manage.py migrate
   python manage.py test
   ```

3. **Multi-Stage Docker Build Tests**
   ```bash
   # Build and test optimized image
   DOCKER_BUILDKIT=1 docker build -t receipt-optimized .
   docker run -d -p 8000:8000 --name receipt-test receipt-optimized
   curl -f http://localhost:8000/ || echo "Health check failed"
   docker stop receipt-test && docker rm receipt-test
   ```

4. **Static Files Tests**
   ```bash
   python manage.py collectstatic --noinput --clear
   ```

5. **Production Configuration Tests**
   ```bash
   export DEBUG="False"
   export DATABASE_URL="postgres://user:pass@localhost:5432/testdb"
   python manage.py check --deploy
   ```

6. **Integration Tests**
   ```bash
   export INTEGRATION_TEST_REAL_OPENAI_OCR=false
   pytest -m integration
   ```

7. **JavaScript Tests**
   ```bash
   npm test
   ```

## Success Criteria

### Must Pass:
- ✅ All existing Django tests pass
- ✅ All integration tests pass
- ✅ All JavaScript tests pass
- ✅ All OCR library tests pass
- ✅ Static file collection works
- ✅ No dependency conflicts
- ✅ No deployment check warnings in production mode

### Should Work:
- ✅ App starts with both SQLite and PostgreSQL URLs
- ✅ WhiteNoise serves static files correctly
- ✅ Security headers configured properly
- ✅ CSRF protection works with .fly.dev domains

## Rollback Plan

If tests fail:
1. Identify which change caused the failure
2. Revert specific changes:
   - Database configuration in settings.py
   - Middleware configuration
   - Dependencies in requirements.txt
3. Run tests again to confirm rollback works
4. Fix issues incrementally

## Notes

- PostgreSQL tests are simulated since actual PostgreSQL connection isn't available locally
- Real PostgreSQL testing will happen during actual Fly.io deployment
- All existing functionality must continue to work unchanged
- New deployment features should be additive, not breaking changes