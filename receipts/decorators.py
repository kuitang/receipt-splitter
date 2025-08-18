"""
Rate limit decorators for views using django-ratelimit.
Centralized configuration for different endpoint types.
"""
from functools import wraps
from django.conf import settings
from django_ratelimit.decorators import ratelimit

def conditional_ratelimit(key, rate, method):
    """Apply rate limiting only if RATELIMIT_ENABLE is True"""
    def decorator(func):
        if getattr(settings, 'RATELIMIT_ENABLE', True):
            return ratelimit(key=key, rate=rate, method=method)(func)
        return func
    return decorator

# Predefined rate limit decorators for different endpoint types
rate_limit_upload = conditional_ratelimit(key='ip', rate='10/h', method='POST')
rate_limit_edit = conditional_ratelimit(key='ip', rate='30/m', method='POST')
rate_limit_view = conditional_ratelimit(key='ip', rate='200/m', method='GET')
rate_limit_claim = conditional_ratelimit(key='ip', rate='50/m', method='POST')
rate_limit_finalize = conditional_ratelimit(key='ip', rate='5/m', method='POST')