"""
Context processors for weather app
"""
from django.conf import settings
import os

def weather_settings(request):
    """
    Context processor to add weather-related settings to all templates
    """
    context = {
        'WEATHER_API_KEY': getattr(settings, 'WEATHER_API_KEY', ''),
        'WEATHER_API_URL': getattr(settings, 'WEATHER_API_URL', ''),
        'MAPBOX_TOKEN': getattr(settings, 'MAPBOX_TOKEN', ''),
        'DEBUG': settings.DEBUG,
        'current_year': __import__('datetime').datetime.now().year,
    }
    
    # Add user-specific settings if authenticated
    if request.user.is_authenticated:
        try:
            from .models import UserSettings
            user_settings, created = UserSettings.objects.get_or_create(user=request.user)
            context.update({
                'user_temperature_unit': user_settings.temperature_unit,
                'user_theme': user_settings.theme,
                'user_time_format': user_settings.time_format,
                'user_wind_speed_unit': user_settings.wind_speed_unit,
                'user_show_map': user_settings.show_map,
                'user_show_air_quality': user_settings.show_air_quality,
                'user_show_alerts': user_settings.show_alerts,
                'user_auto_refresh': user_settings.auto_refresh,
                'user_refresh_interval': user_settings.refresh_interval,
            })
        except Exception as e:
            # Fallback to defaults if there's an error
            context.update({
                'user_temperature_unit': 'celsius',
                'user_theme': 'auto',
                'user_time_format': '24h',
                'user_wind_speed_unit': 'metric',
                'user_show_map': True,
                'user_show_air_quality': True,
                'user_show_alerts': True,
                'user_auto_refresh': False,
                'user_refresh_interval': 30,
            })
    else:
        # Default values for anonymous users
        context.update({
            'user_temperature_unit': request.session.get('temperature_unit', 'celsius'),
            'user_theme': request.session.get('theme', 'auto'),
            'user_time_format': request.session.get('time_format', '24h'),
            'user_wind_speed_unit': request.session.get('wind_speed_unit', 'metric'),
            'user_show_map': True,
            'user_show_air_quality': True,
            'user_show_alerts': True,
            'user_auto_refresh': False,
            'user_refresh_interval': 30,
        })
    
    return context

def featured_cities(request):
    """
    Context processor to provide featured cities
    """
    return {
        'featured_cities': [
            {'name': 'New York', 'country': 'US', 'lat': 40.7128, 'lon': -74.0060},
            {'name': 'London', 'country': 'GB', 'lat': 51.5074, 'lon': -0.1278},
            {'name': 'Tokyo', 'country': 'JP', 'lat': 35.6762, 'lon': 139.6503},
            {'name': 'Paris', 'country': 'FR', 'lat': 48.8566, 'lon': 2.3522},
            {'name': 'Sydney', 'country': 'AU', 'lat': -33.8688, 'lon': 151.2093},
            {'name': 'Dubai', 'country': 'AE', 'lat': 25.2048, 'lon': 55.2708},
            {'name': 'Singapore', 'country': 'SG', 'lat': 1.3521, 'lon': 103.8198},
            {'name': 'Mumbai', 'country': 'IN', 'lat': 19.0760, 'lon': 72.8777},
        ]
    }

def current_year(request):
    """
    Context processor to provide current year
    """
    from django.utils import timezone
    return {'current_year': timezone.now().year}

def app_version(request):
    """
    Context processor to provide app version
    """
    return {'APP_VERSION': '2.0.0'}