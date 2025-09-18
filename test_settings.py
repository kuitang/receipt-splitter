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

if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS'].update({
        'timeout': 30,
        'check_same_thread': False,
    })

# Ensure test mode
DEBUG = False
TESTING = True

# Use simple static files storage for tests, no hashing
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Disable async processing for tests to avoid threading issues with SQLite
USE_ASYNC_PROCESSING = False
