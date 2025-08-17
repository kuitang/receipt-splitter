"""
Rate limit decorators for views using django-ratelimit.
Centralized configuration for different endpoint types.
"""
from django_ratelimit.decorators import ratelimit

# Predefined rate limit decorators for different endpoint types
rate_limit_upload = ratelimit(key='ip', rate='10/h', method='POST')
rate_limit_edit = ratelimit(key='ip', rate='30/m', method='POST')
rate_limit_view = ratelimit(key='ip', rate='200/m', method='GET')
rate_limit_claim = ratelimit(key='ip', rate='50/m', method='POST')
rate_limit_finalize = ratelimit(key='ip', rate='5/m', method='POST')