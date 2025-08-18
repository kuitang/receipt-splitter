"""
Query Performance Monitoring Middleware
Tracks database query counts and response times to prevent performance regressions
"""
import time
import logging
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)


class QueryPerformanceMiddleware:
    """
    Middleware to monitor database query performance
    Logs warnings when query count or response time exceeds thresholds
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Configuration thresholds
        self.query_threshold = getattr(settings, 'QUERY_COUNT_THRESHOLD', 10)
        self.response_time_threshold = getattr(settings, 'RESPONSE_TIME_THRESHOLD_MS', 200)
    
    def __call__(self, request):
        # Record start state
        start_time = time.time()
        start_queries = len(connection.queries)
        
        # Process request
        response = self.get_response(request)
        
        # Calculate performance metrics
        end_time = time.time()
        end_queries = len(connection.queries)
        
        query_count = end_queries - start_queries
        response_time_ms = (end_time - start_time) * 1000
        
        # Add headers for debugging
        response['X-Query-Count'] = str(query_count)
        response['X-Response-Time-Ms'] = f"{response_time_ms:.2f}"
        
        # Log performance warnings
        if query_count > self.query_threshold:
            logger.warning(
                f"High query count: {query_count} queries for {request.path} "
                f"(threshold: {self.query_threshold})"
            )
            
            # Log actual queries in debug mode
            if settings.DEBUG and hasattr(settings, 'LOG_SLOW_QUERIES'):
                recent_queries = connection.queries[start_queries:end_queries]
                for i, query in enumerate(recent_queries, 1):
                    logger.warning(f"Query {i}: {query['sql'][:200]}...")
        
        if response_time_ms > self.response_time_threshold:
            logger.warning(
                f"Slow response: {response_time_ms:.2f}ms for {request.path} "
                f"(threshold: {self.response_time_threshold}ms)"
            )
        
        # Log summary for performance-critical endpoints
        if query_count > 5 or response_time_ms > 100:
            logger.info(
                f"Performance: {request.path} - {query_count} queries, "
                f"{response_time_ms:.2f}ms"
            )
        
        return response


def log_query_performance(func):
    """
    Decorator to track query performance for individual functions
    Useful for monitoring service layer methods
    """
    def wrapper(*args, **kwargs):
        if not settings.DEBUG:
            return func(*args, **kwargs)
            
        start_time = time.time()
        start_queries = len(connection.queries)
        
        result = func(*args, **kwargs)
        
        end_time = time.time()
        end_queries = len(connection.queries)
        
        duration = (end_time - start_time) * 1000  # ms
        query_count = end_queries - start_queries
        
        if duration > 100 or query_count > 5:
            logger.info(
                f"{func.__name__}: {duration:.2f}ms, {query_count} queries"
            )
            
            if query_count > 10:
                logger.warning(
                    f"High query count in {func.__name__}: {query_count} queries"
                )
        
        return result
    return wrapper