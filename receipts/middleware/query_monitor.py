"""
Query monitoring middleware to track and log database performance
Helps prevent performance regressions by alerting on high query counts
"""
import logging
import time
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)


class QueryCountMiddleware:
    """
    Middleware to count and log database queries per request
    Adds X-Query-Count header and logs warnings for high query counts
    """
    
    # Threshold for warning about high query count
    QUERY_COUNT_WARNING_THRESHOLD = 10
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Only monitor in DEBUG mode to avoid production overhead
        if not settings.DEBUG:
            return self.get_response(request)
            
        # Reset queries at start of request
        connection.queries_log.clear()
        
        # Track start state
        start_time = time.time()
        queries_before = len(connection.queries)
        
        # Process request
        response = self.get_response(request)
        
        # Calculate metrics
        end_time = time.time()
        queries_after = len(connection.queries)
        query_count = queries_after - queries_before
        duration_ms = (end_time - start_time) * 1000
        
        # Add query count to response header
        response['X-Query-Count'] = str(query_count)
        response['X-Response-Time-Ms'] = f"{duration_ms:.2f}"
        
        # Log warning if query count is high
        if query_count > self.QUERY_COUNT_WARNING_THRESHOLD:
            logger.warning(
                f"High query count: {query_count} queries in {duration_ms:.2f}ms for {request.method} {request.path}"
            )
            
            # Log details of queries if very high
            if query_count > 20:
                logger.warning("Query details (first 5):")
                for query in connection.queries[:5]:
                    logger.warning(f"  - {query['time']}s: {query['sql'][:100]}...")
        
        # Log info for slow requests
        elif duration_ms > 500:
            logger.info(
                f"Slow request: {duration_ms:.2f}ms with {query_count} queries for {request.method} {request.path}"
            )
        
        return response


def log_query_performance(func):
    """
    Decorator to log query performance for specific functions
    Useful for monitoring critical service methods
    """
    def wrapper(*args, **kwargs):
        if not settings.DEBUG:
            return func(*args, **kwargs)
            
        start_time = time.time()
        start_queries = len(connection.queries)
        
        try:
            result = func(*args, **kwargs)
        finally:
            end_time = time.time()
            end_queries = len(connection.queries)
            
            duration_ms = (end_time - start_time) * 1000
            query_count = end_queries - start_queries
            
            # Log if slow or many queries
            if duration_ms > 100 or query_count > 5:
                logger.info(
                    f"{func.__module__}.{func.__name__}: {duration_ms:.2f}ms, {query_count} queries"
                )
                
                # Log warning for particularly bad performance
                if duration_ms > 500 or query_count > 15:
                    logger.warning(
                        f"Performance issue in {func.__module__}.{func.__name__}: "
                        f"{duration_ms:.2f}ms, {query_count} queries"
                    )
        
        return result
    
    return wrapper