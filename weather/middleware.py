"""
Custom middleware for weather app
"""
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

class WeatherMiddleware:
    """Custom middleware for weather app functionality"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization
        
    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        
        # Add current time to request
        request.current_time = timezone.now()
        
        # Add user preference for temperature unit to session
        if request.user.is_authenticated:
            try:
                from .models import UserSettings
                settings, created = UserSettings.objects.get_or_create(user=request.user)
                request.temperature_unit = settings.temperature_unit
                request.theme = settings.theme
            except Exception as e:
                logger.error(f"Error loading user settings: {e}")
                request.temperature_unit = 'celsius'
                request.theme = 'auto'
        else:
            request.temperature_unit = request.session.get('temperature_unit', 'celsius')
            request.theme = request.session.get('theme', 'auto')
        
        response = self.get_response(request)
        
        # Code to be executed for each request/response after
        # the view is called.
        
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Called just before Django calls the view"""
        # Add any pre-view processing here
        return None
    
    def process_exception(self, request, exception):
        """Called when a view raises an exception"""
        logger.error(f"Unhandled exception: {exception}")
        return None
    
    def process_template_response(self, request, response):
        """Called when a response has a .render() method"""
        # Add additional context to template responses
        if hasattr(response, 'context_data'):
            response.context_data['current_year'] = timezone.now().year
            response.context_data['temperature_unit'] = getattr(request, 'temperature_unit', 'celsius')
            response.context_data['theme'] = getattr(request, 'theme', 'auto')
        return response