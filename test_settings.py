"""Test-specific Django settings"""
from receipt_splitter.settings import *

# Disable rate limiting for tests
RATELIMIT_ENABLE = False

# Use in-memory cache for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Ensure test mode
DEBUG = True
TESTING = True