from functools import wraps
from django.http import JsonResponse
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from .models import APILog
import time
import hashlib
import logging

logger = logging.getLogger(__name__)

def api_response_time(view_func):
    """Decorator to measure API response time"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        start_time = time.time()
        response = view_func(request, *args, **kwargs)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Log API call
        try:
            APILog.objects.create(
                endpoint=request.path,
                method=request.method,
                user=request.user if request.user.is_authenticated else None,
                ip_address=request.META.get('REMOTE_ADDR'),
                response_time=response_time,
                status_code=response.status_code
            )
        except Exception as e:
            logger.error(f"Failed to log API call: {e}")
        
        # Add response time header
        response['X-Response-Time'] = str(round(response_time * 1000, 2)) + 'ms'
        
        return response
    return wrapper

def cache_response(timeout=300):
    """Decorator to cache API responses"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key based on request
            cache_key = hashlib.md5(
                f"{request.path}_{request.GET.urlencode()}_{request.user.id if request.user.is_authenticated else 'anon'}"
                .encode()
            ).hexdigest()
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response:
                response = JsonResponse(cached_response)
                response['X-Cache'] = 'HIT'
                return response
            
            # Execute view
            response = view_func(request, *args, **kwargs)
            
            # Cache if successful
            if response.status_code == 200:
                try:
                    cache.set(cache_key, response.json(), timeout)
                except:
                    pass
            
            response['X-Cache'] = 'MISS'
            return response
        return wrapper
    return decorator

def rate_limit(key='ip', rate='100/h'):
    """Decorator to rate limit API endpoints"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get rate limit key
            if key == 'ip':
                limit_key = request.META.get('REMOTE_ADDR')
            elif key == 'user' and request.user.is_authenticated:
                limit_key = f"user_{request.user.id}"
            else:
                limit_key = request.META.get('REMOTE_ADDR')
            
            # Parse rate (e.g., '100/h' -> 100, 3600)
            try:
                count, period = rate.split('/')
                count = int(count)
                if period == 'h':
                    seconds = 3600
                elif period == 'm':
                    seconds = 60
                elif period == 'd':
                    seconds = 86400
                else:
                    seconds = 3600
            except:
                count, seconds = 100, 3600
            
            # Check rate limit
            cache_key = f"rate_limit_{limit_key}_{request.path}"
            current = cache.get(cache_key, 0)
            
            if current >= count:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {count} requests per {period}'
                }, status=429)
            
            # Increment counter
            cache.set(cache_key, current + 1, seconds)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def require_api_key(view_func):
    """Decorator to require API key for access"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
        
        if not api_key:
            return JsonResponse({
                'error': 'API key required',
                'message': 'Please provide an API key in X-API-Key header or api_key parameter'
            }, status=401)
        
        # Validate API key (implement your validation logic)
        if api_key != settings.API_KEY and api_key != settings.WEATHER_API_KEY:
            return JsonResponse({
                'error': 'Invalid API key'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    return wrapper

def log_activity(view_func):
    """Decorator to log user activity"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        
        if request.user.is_authenticated:
            logger.info(
                f"User {request.user.username} accessed {request.path} "
                f"[{request.method}] - {response.status_code}"
            )
        
        return response
    return wrapper

def handle_errors(view_func):
    """Decorator to handle exceptions gracefully"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {view_func.__name__}: {e}", exc_info=True)
            return JsonResponse({
                'error': 'Internal server error',
                'message': str(e) if settings.DEBUG else 'An unexpected error occurred'
            }, status=500)
    return wrapper

def validate_city(view_func):
    """Decorator to validate city parameter"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        city = request.GET.get('city', '').strip()
        
        if not city:
            return JsonResponse({
                'error': 'City parameter is required'
            }, status=400)
        
        if len(city) < 2:
            return JsonResponse({
                'error': 'City name must be at least 2 characters long'
            }, status=400)
        
        return view_func(request, *args, **kwargs)
    return wrapper

def check_maintenance_mode(view_func):
    """Decorator to check if site is in maintenance mode"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if getattr(settings, 'MAINTENANCE_MODE', False):
            return JsonResponse({
                'error': 'Service temporarily unavailable',
                'message': 'The system is under maintenance. Please try again later.'
            }, status=503)
        return view_func(request, *args, **kwargs)
    return wrapper