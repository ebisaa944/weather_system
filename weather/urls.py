"""
Weather app URL configuration.
Separates web interfaces and API endpoints with proper namespacing.
"""
from django.urls import path, include  # Fixed: include comes from django.urls, not django.conf
from django.views.generic import TemplateView  # Added missing import
from django.conf import settings  # This is correct for settings import
from . import views

app_name = 'weather'

# Web Interface URLs
web_patterns = [
    # Home and main pages
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('map/', views.weather_map, name='weather_map'),
    path('alerts/', views.weather_alerts, name='weather_alerts'),
    
    # User management
    path('settings/', views.user_settings, name='settings'),
    path('history/', views.search_history, name='search_history'),
    path('favorites/', views.favorite_cities, name='favorite_cities'),
    
    # Static pages
    path('about/', TemplateView.as_view(template_name='weather/about.html'), name='about'),
    path('contact/', TemplateView.as_view(template_name='weather/contact.html'), name='contact'),
    path('privacy/', TemplateView.as_view(template_name='weather/privacy.html'), name='privacy'),
    path('terms/', TemplateView.as_view(template_name='weather/terms.html'), name='terms'),
    path('debug/env/', views.debug_env, name='debug_env'),
    path('test-api/', views.test_weather_api, name='test_api'),
]

# API v2 URLs (RESTful)
api_v2_patterns = [
    # Current Weather
    path('weather/current/', 
         views.get_current_weather, 
         name='api_current_weather'),
    
    path('weather/current/coords/', 
         views.get_weather_by_coords, 
         name='api_weather_coords'),
    
    path('weather/current/multiple/', 
         views.get_multiple_cities_weather, 
         name='api_multiple_cities'),
    
    # Forecast
    path('weather/forecast/', 
         views.get_forecast, 
         name='api_forecast'),
    
    path('weather/forecast/hourly/', 
         views.get_hourly_forecast, 
         name='api_hourly_forecast'),
    
    # Search and Location
    path('weather/search/', 
         views.search_cities, 
         name='api_search'),
    
    path('weather/geocode/', 
         views.geocode_location, 
         name='api_geocode'),
    
    path('weather/reverse-geocode/', 
         views.reverse_geocode, 
         name='api_reverse_geocode'),
    
    # Air Quality
    path('weather/air-quality/', 
         views.get_air_quality, 
         name='api_air_quality'),
    
    path('weather/air-quality/history/', 
         views.get_air_quality_history, 
         name='api_air_quality_history'),
    
    # Historical Data
    path('weather/historical/', 
         views.get_historical_data, 
         name='api_historical'),
    
    path('weather/statistics/', 
         views.get_weather_statistics, 
         name='api_statistics'),
    
    # Alerts
    path('weather/alerts/', 
         views.get_weather_alerts, 
         name='api_alerts'),
    
    path('weather/alerts/subscribe/', 
         views.subscribe_alerts, 
         name='api_subscribe_alerts'),
    
    # User Data (authenticated)
    path('user/favorites/', 
         views.user_favorites_api, 
         name='api_favorites'),
    
    path('user/settings/', 
         views.user_settings_api, 
         name='api_settings'),
]

# Combine all patterns
urlpatterns = web_patterns + api_v2_patterns

# API v1 URLs (backward compatibility)
api_v1_patterns = [
    path('v1/', include((api_v2_patterns, 'weather'), namespace='v1')),
]

# Add v1 patterns if needed (optional)
if settings.DEBUG:
    urlpatterns += api_v1_patterns