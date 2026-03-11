from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
import json
import logging
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Try to import advanced service, fall back to simple if not available
try:
    from .weather_service_advanced import AdvancedWeatherService
    WEATHER_SERVICE_AVAILABLE = True
except ImportError:
    from .weather_service_simple import SimpleWeatherService
    AdvancedWeatherService = SimpleWeatherService
    WEATHER_SERVICE_AVAILABLE = False
    logger.warning("Advanced weather service not available, using simple service")

from .models import SearchHistory, FavoriteCity, WeatherAlert, UserSettings
from .serializers import (
    CurrentWeatherSerializer, ForecastSerializer, 
    AirQualitySerializer, FavoriteCitySerializer,
    UserSettingsSerializer
)
from .decorators import (
    api_response_time, cache_response, rate_limit,
    validate_city, handle_errors
)
from .utils import WeatherUtils, DataFormatter

# Initialize services
try:
    weather_service = AdvancedWeatherService()
except Exception as e:
    logger.error(f"Failed to initialize weather service: {e}")
    from .weather_service_simple import SimpleWeatherService
    weather_service = SimpleWeatherService()

utils = WeatherUtils()
formatter = DataFormatter()

# Helper function to run async functions in sync context
def run_async(coro):
    """Run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # If loop is already running, create a new task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return loop.run_until_complete(coro)

# Web Views
@ensure_csrf_cookie
def home(request):
    """Home page view"""
    context = {
        'title': 'Weather System - Home',
        'featured_cities': ['New York', 'London', 'Tokyo', 'Sydney', 'Paris', 'Dubai']
    }
    return render(request, 'weather/index.html', context)

@login_required
def dashboard(request):
    """User dashboard view"""
    # Get user's favorite cities
    favorites = FavoriteCity.objects.filter(user=request.user, is_active=True)
    
    # Get recent searches
    recent_searches = SearchHistory.objects.filter(user=request.user)[:10]
    
    # Get user settings
    user_settings, created = UserSettings.objects.get_or_create(user=request.user)
    
    context = {
        'title': 'Dashboard - Weather System',
        'favorites': favorites,
        'recent_searches': recent_searches,
        'settings': user_settings
    }
    return render(request, 'weather/dashboard.html', context)

def weather_map(request):
    """Interactive weather map view"""
    context = {
        'title': 'Weather Map - Weather System',
        'mapbox_token': getattr(settings, 'MAPBOX_TOKEN', '')
    }
    return render(request, 'weather/map_view.html', context)

def weather_alerts(request):
    """Weather alerts view"""
    # Get active alerts
    active_alerts = WeatherAlert.objects.filter(
        end_time__gte=timezone.now()
    ).order_by('-severity', '-start_time')[:50]
    
    context = {
        'title': 'Weather Alerts - Weather System',
        'alerts': active_alerts
    }
    return render(request, 'weather/alerts.html', context)

@login_required
def user_settings(request):
    """User settings view"""
    user_settings, created = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Handle form submission
        temperature_unit = request.POST.get('temperature_unit')
        if temperature_unit:
            user_settings.temperature_unit = temperature_unit
        
        theme = request.POST.get('theme')
        if theme:
            user_settings.theme = theme
        
        email_notifications = request.POST.get('email_notifications') == 'on'
        user_settings.email_notifications = email_notifications
        
        user_settings.save()
        messages.success(request, 'Settings updated successfully!')
        return redirect('weather:settings')
    
    context = {
        'title': 'Settings - Weather System',
        'settings': user_settings
    }
    return render(request, 'weather/settings.html', context)

@login_required
def search_history(request):
    """User search history view"""
    history = SearchHistory.objects.filter(user=request.user)
    
    # Pagination
    paginator = Paginator(history, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Search History - Weather System',
        'page_obj': page_obj
    }
    return render(request, 'weather/history.html', context)

@login_required
def favorite_cities(request):
    """User favorite cities view"""
    favorites = FavoriteCity.objects.filter(user=request.user)
    
    if request.method == 'POST':
        # Add new favorite
        city_name = request.POST.get('city_name')
        if city_name:
            FavoriteCity.objects.create(
                user=request.user,
                city_name=city_name
            )
            messages.success(request, f'{city_name} added to favorites!')
        return redirect('weather:favorite_cities')
    
    context = {
        'title': 'Favorite Cities - Weather System',
        'favorites': favorites
    }
    return render(request, 'weather/favorites.html', context)

@login_required
def remove_favorite(request, favorite_id):
    """Remove favorite city"""
    favorite = get_object_or_404(FavoriteCity, id=favorite_id, user=request.user)
    favorite.delete()
    messages.success(request, f'{favorite.city_name} removed from favorites')
    return redirect('weather:favorite_cities')

# API Views - Current Weather
@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='60/h')
@handle_errors
def get_current_weather(request):
    """API endpoint to get current weather (sync version)"""
    city = request.GET.get('city', '').strip()
    
    if not city:
        return JsonResponse({'success': False, 'error': 'City is required'}, status=400)
    
    # Save search history if user is authenticated
    if request.user.is_authenticated:
        SearchHistory.objects.create(
            user=request.user,
            city_name=city,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
    
    # Use sync method or run async
    if hasattr(weather_service, 'get_current_weather_sync'):
        result = weather_service.get_current_weather_sync(city)
    else:
        # Fallback to mock data
        result = {
            'success': True,
            'data': {
                'city': city,
                'country': 'US',
                'temperature': random.randint(15, 30),
                'feels_like': random.randint(15, 30),
                'humidity': random.randint(40, 90),
                'pressure': random.randint(1000, 1020),
                'description': random.choice(['Sunny', 'Partly cloudy', 'Cloudy', 'Light rain']),
                'icon': random.choice(['01d', '02d', '03d', '10d']),
                'wind_speed': round(random.uniform(0, 10), 1),
                'wind_direction': random.randint(0, 360),
                'clouds': random.randint(0, 100),
                'visibility': random.randint(5000, 10000),
                'sunrise': int(datetime.now().replace(hour=6, minute=0).timestamp()),
                'sunset': int(datetime.now().replace(hour=18, minute=0).timestamp()),
                'coordinates': {'lat': 40.7128, 'lon': -74.0060},
                'uv_index': round(random.uniform(0, 8), 1)
            }
        }
    
    return JsonResponse(result)

@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='60/h')
@handle_errors
def get_weather_by_coords(request):
    """Get weather by coordinates"""
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({
            'success': False, 
            'error': 'Latitude and longitude are required'
        }, status=400)
    
    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid coordinates'
        }, status=400)
    
    # Mock response for now
    return JsonResponse({
        'success': True,
        'data': {
            'city': 'Location from coordinates',
            'country': 'US',
            'temperature': 22,
            'feels_like': 21,
            'humidity': 65,
            'description': 'Sunny',
            'icon': '01d',
            'wind_speed': 5.2,
            'coordinates': {'lat': lat, 'lon': lon}
        }
    })

@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def get_multiple_cities_weather(request):
    """Get weather for multiple cities"""
    cities = request.GET.getlist('cities[]')
    
    if not cities or len(cities) > 10:
        return JsonResponse({
            'success': False,
            'error': 'Please provide 1-10 cities'
        }, status=400)
    
    weather_data = []
    for city in cities:
        weather_data.append({
            'city': city,
            'temperature': random.randint(15, 30),
            'description': random.choice(['Sunny', 'Cloudy', 'Rainy']),
            'humidity': random.randint(40, 90)
        })
    
    return JsonResponse({
        'success': True,
        'data': weather_data
    })

# API Views - Forecast
@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def get_forecast(request):
    """Get weather forecast"""
    city = request.GET.get('city', '').strip()
    days = int(request.GET.get('days', 5))
    
    if not city:
        return JsonResponse({'success': False, 'error': 'City is required'}, status=400)
    
    if days < 1 or days > 7:
        days = 5
    
    # Mock forecast data
    forecast_data = []
    start_date = datetime.now()
    
    for i in range(days):
        date = start_date + timedelta(days=i)
        forecast_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'day_name': date.strftime('%A'),
            'temp_min': random.randint(15, 20),
            'temp_max': random.randint(21, 28),
            'humidity': random.randint(50, 85),
            'description': random.choice(['Sunny', 'Partly cloudy', 'Cloudy', 'Light rain']),
            'icon': random.choice(['01d', '02d', '03d', '10d']),
            'wind_speed': round(random.uniform(2, 8), 1),
            'pop': random.randint(0, 60)
        })
    
    return JsonResponse({
        'success': True,
        'data': {
            'city': city,
            'country': 'US',
            'forecast': forecast_data
        }
    })

@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def get_hourly_forecast(request):
    """Get hourly forecast"""
    city = request.GET.get('city', '').strip()
    hours = int(request.GET.get('hours', 24))
    
    if not city:
        return JsonResponse({'success': False, 'error': 'City is required'}, status=400)
    
    if hours < 1 or hours > 48:
        hours = 24
    
    # Mock hourly forecast
    hourly_data = []
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    
    for i in range(hours):
        time = start_time + timedelta(hours=i)
        hourly_data.append({
            'time': time.strftime('%H:00'),
            'temperature': random.randint(18, 25),
            'description': random.choice(['Clear', 'Cloudy', 'Light rain']),
            'pop': random.randint(0, 40)
        })
    
    return JsonResponse({
        'success': True,
        'data': {
            'city': city,
            'hourly': hourly_data
        }
    })

# API Views - Search and Location
@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='60/h')
@handle_errors
def search_cities(request):
    """Search for cities"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'success': True, 'data': []})
    
    # Mock city data
    mock_cities = [
        {'name': 'London', 'country': 'GB', 'lat': 51.5074, 'lon': -0.1278},
        {'name': 'Los Angeles', 'country': 'US', 'lat': 34.0522, 'lon': -118.2437},
        {'name': 'Paris', 'country': 'FR', 'lat': 48.8566, 'lon': 2.3522},
        {'name': 'Tokyo', 'country': 'JP', 'lat': 35.6762, 'lon': 139.6503},
        {'name': 'Sydney', 'country': 'AU', 'lat': -33.8688, 'lon': 151.2093},
        {'name': 'New York', 'country': 'US', 'lat': 40.7128, 'lon': -74.0060},
        {'name': 'Dubai', 'country': 'AE', 'lat': 25.2048, 'lon': 55.2708},
        {'name': 'Singapore', 'country': 'SG', 'lat': 1.3521, 'lon': 103.8198},
        {'name': 'Mumbai', 'country': 'IN', 'lat': 19.0760, 'lon': 72.8777},
        {'name': 'Moscow', 'country': 'RU', 'lat': 55.7558, 'lon': 37.6173},
    ]
    
    results = [city for city in mock_cities if query.lower() in city['name'].lower()]
    return JsonResponse({'success': True, 'data': results})

@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def geocode_location(request):
    """Geocode location name to coordinates"""
    location = request.GET.get('location', '').strip()
    
    if not location:
        return JsonResponse({
            'success': False, 
            'error': 'Location is required'
        }, status=400)
    
    # Mock geocoding
    mock_locations = {
        'london': {'lat': 51.5074, 'lon': -0.1278, 'country': 'GB'},
        'paris': {'lat': 48.8566, 'lon': 2.3522, 'country': 'FR'},
        'new york': {'lat': 40.7128, 'lon': -74.0060, 'country': 'US'},
        'tokyo': {'lat': 35.6762, 'lon': 139.6503, 'country': 'JP'},
        'sydney': {'lat': -33.8688, 'lon': 151.2093, 'country': 'AU'},
    }
    
    location_key = location.lower()
    if location_key in mock_locations:
        data = mock_locations[location_key]
        return JsonResponse({
            'success': True,
            'data': {
                'location': location,
                'lat': data['lat'],
                'lon': data['lon'],
                'country': data['country']
            }
        })
    
    return JsonResponse({
        'success': False,
        'error': 'Location not found'
    }, status=404)

@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def reverse_geocode(request):
    """Reverse geocode coordinates to location name"""
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({
            'success': False, 
            'error': 'Latitude and longitude are required'
        }, status=400)
    
    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid coordinates'
        }, status=400)
    
    # Mock reverse geocoding
    return JsonResponse({
        'success': True,
        'data': {
            'lat': lat,
            'lon': lon,
            'location': 'Sample City',
            'country': 'Sample Country'
        }
    })

# API Views - Air Quality
@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def get_air_quality(request):
    """Get air quality data"""
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({
            'success': False, 
            'error': 'Latitude and longitude are required'
        }, status=400)
    
    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid coordinates'
        }, status=400)
    
    # Mock air quality data
    aqi = random.randint(1, 5)
    aqi_labels = ['Good', 'Fair', 'Moderate', 'Poor', 'Very Poor']
    
    return JsonResponse({
        'success': True,
        'data': {
            'aqi': aqi,
            'aqi_label': aqi_labels[aqi - 1],
            'components': {
                'co': round(random.uniform(200, 500), 1),
                'no': round(random.uniform(0, 50), 1),
                'no2': round(random.uniform(10, 80), 1),
                'o3': round(random.uniform(20, 100), 1),
                'so2': round(random.uniform(0, 20), 1),
                'pm2_5': round(random.uniform(5, 35), 1),
                'pm10': round(random.uniform(10, 50), 1),
                'nh3': round(random.uniform(0, 10), 1)
            }
        }
    })


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='20/h')
@handle_errors
def get_air_quality_history(request):
    """Get air quality history for a location"""
    city = request.GET.get('city', '').strip()
    days = int(request.GET.get('days', 7))
    
    if not city:
        return JsonResponse({'success': False, 'error': 'City is required'}, status=400)
    
    if days < 1 or days > 30:
        days = 7
    
    # Mock historical air quality data
    history = []
    aqi_labels = ['Good', 'Fair', 'Moderate', 'Poor', 'Very Poor']
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        aqi = random.randint(1, 5)
        history.append({
            'date': date,
            'aqi': aqi,
            'aqi_label': aqi_labels[aqi - 1],
            'components': {
                'pm2_5': round(random.uniform(5, 35), 1),
                'pm10': round(random.uniform(10, 50), 1),
                'o3': round(random.uniform(20, 100), 1),
                'no2': round(random.uniform(10, 80), 1),
                'so2': round(random.uniform(0, 20), 1),
                'co': round(random.uniform(200, 500), 1)
            }
        })
    
    return JsonResponse({
        'success': True,
        'data': {
            'city': city,
            'days': days,
            'history': history
        }
    })

# API Views - Historical Data
@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='20/h')
@handle_errors
def get_historical_data(request):
    """Get historical weather data"""
    city = request.GET.get('city', '').strip()
    days = int(request.GET.get('days', 7))
    
    if not city:
        return JsonResponse({'success': False, 'error': 'City is required'}, status=400)
    
    if days < 1 or days > 30:
        days = 7
    
    # Mock historical data
    history = []
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        history.append({
            'date': date,
            'temp_max': random.randint(22, 28),
            'temp_min': random.randint(15, 21),
            'temp_mean': random.randint(18, 24),
            'precipitation': round(random.uniform(0, 10), 1),
            'wind_max': random.randint(10, 25)
        })
    
    return JsonResponse({
        'success': True,
        'data': {
            'city': city,
            'days': days,
            'data': history
        }
    })

@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='20/h')
@handle_errors
def get_weather_statistics(request):
    """Get weather statistics for a city"""
    city = request.GET.get('city', '').strip()
    
    if not city:
        return JsonResponse({'success': False, 'error': 'City is required'}, status=400)
    
    # Mock statistics
    statistics = {
        'city': city,
        'average_temp': round(random.uniform(10, 25), 1),
        'average_humidity': random.randint(60, 80),
        'rainy_days_per_month': random.randint(5, 15),
        'sunny_days_per_month': random.randint(10, 25),
        'best_time_to_visit': random.choice(['Spring', 'Summer', 'Fall']),
        'climate': random.choice(['Temperate', 'Mediterranean', 'Continental'])
    }
    
    return JsonResponse({
        'success': True,
        'data': statistics
    })

# API Views - Alerts
@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='20/h')
@handle_errors
def get_weather_alerts(request):
    """Get weather alerts for a location"""
    city = request.GET.get('city', '').strip()
    
    if not city:
        return JsonResponse({'success': True, 'data': []})
    
    # Mock alerts
    alerts = []
    if random.choice([True, False]):  # Randomly show alerts
        alerts = [
            {
                'title': 'Heavy Rain Warning',
                'severity': 'moderate',
                'description': 'Heavy rainfall expected in the area',
                'instruction': 'Avoid low-lying areas',
                'start_time': datetime.now().isoformat(),
                'end_time': (datetime.now() + timedelta(days=1)).isoformat(),
                'source': 'Weather Service'
            }
        ]
    
    return JsonResponse({
        'success': True,
        'data': alerts
    })

@require_http_methods(['POST'])
@login_required
@api_response_time
@handle_errors
def subscribe_alerts(request):
    """Subscribe to weather alerts for a city"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST
    
    city = data.get('city')
    
    if not city:
        return JsonResponse({
            'success': False,
            'error': 'City is required'
        }, status=400)
    
    # In a real app, you would save this to the database
    # For now, just return success
    
    return JsonResponse({
        'success': True,
        'message': f'Subscribed to alerts for {city}'
    })

# API Views - User Data
@require_http_methods(['GET', 'POST', 'DELETE'])
@login_required
@api_response_time
@handle_errors
def user_favorites_api(request):
    """API endpoint for user favorites"""
    if request.method == 'GET':
        favorites = FavoriteCity.objects.filter(user=request.user, is_active=True)
        data = [{
            'id': fav.id,
            'city_name': fav.city_name,
            'country': fav.country,
            'added_date': fav.added_date.isoformat() if fav.added_date else None
        } for fav in favorites]
        return JsonResponse({'success': True, 'data': data})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST
        
        city_name = data.get('city_name')
        if not city_name:
            return JsonResponse({
                'success': False,
                'error': 'City name is required'
            }, status=400)
        
        favorite, created = FavoriteCity.objects.get_or_create(
            user=request.user,
            city_name=city_name,
            defaults={'country': data.get('country', '')}
        )
        
        if not created:
            favorite.is_active = True
            favorite.save()
        
        return JsonResponse({
            'success': True,
            'message': f'{city_name} added to favorites',
            'data': {'id': favorite.id, 'city_name': favorite.city_name}
        }, status=201)
    
    elif request.method == 'DELETE':
        favorite_id = request.GET.get('id')
        if not favorite_id:
            return JsonResponse({
                'success': False,
                'error': 'Favorite ID is required'
            }, status=400)
        
        try:
            favorite = FavoriteCity.objects.get(id=favorite_id, user=request.user)
            favorite.delete()
            return JsonResponse({
                'success': True,
                'message': 'Favorite removed'
            })
        except FavoriteCity.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Favorite not found'
            }, status=404)

@require_http_methods(['GET', 'PUT'])
@login_required
@api_response_time
@handle_errors
def user_settings_api(request):
    """API endpoint for user settings"""
    user_settings, created = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'GET':
        data = {
            'temperature_unit': user_settings.temperature_unit,
            'wind_speed_unit': user_settings.wind_speed_unit,
            'time_format': user_settings.time_format,
            'theme': user_settings.theme,
            'email_notifications': user_settings.email_notifications,
            'push_notifications': user_settings.push_notifications,
            'alert_threshold': user_settings.alert_threshold,
            'default_city': user_settings.default_city,
            'default_country': user_settings.default_country,
            'show_map': user_settings.show_map,
            'show_air_quality': user_settings.show_air_quality,
            'show_alerts': user_settings.show_alerts,
            'auto_refresh': user_settings.auto_refresh,
            'refresh_interval': user_settings.refresh_interval
        }
        return JsonResponse({'success': True, 'data': data})
    
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST
        
        # Update fields
        for field in ['temperature_unit', 'wind_speed_unit', 'time_format', 'theme',
                     'email_notifications', 'push_notifications', 'alert_threshold',
                     'default_city', 'default_country', 'show_map', 'show_air_quality',
                     'show_alerts', 'auto_refresh', 'refresh_interval']:
            if field in data:
                setattr(user_settings, field, data[field])
        
        user_settings.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Settings updated successfully'
        })

# Error handler
def ratelimit_error(request, exception):
    """Rate limit error handler"""
    return JsonResponse({
        'success': False,
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.'
    }, status=429)

# Health check endpoint
def health_check(request):
    """Health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'Weather System',
        'timestamp': datetime.now().isoformat()
    })


from .env_check import check_env_variables, get_weather_api_config, get_safe_api_config, get_system_info, get_all_env_info

def debug_env(request):
    """Debug view to check environment variables"""
    if not settings.DEBUG:
        return JsonResponse({'error': 'Debug mode only'}, status=403)
    
    env_info = get_all_env_info()
    
    return JsonResponse(env_info, json_dumps_params={'indent': 2})


import aiohttp
import asyncio
from django.http import JsonResponse

async def test_weather_api(request):
    """Test the weather API with actual API calls"""
    city = request.GET.get('city', 'London')
    
    # Get API key from settings
    api_key = getattr(settings, 'WEATHER_API_KEY', '')
    
    if not api_key:
        return JsonResponse({
            'success': False,
            'error': 'No API key found',
            'api_key_present': False
        })
    
    try:
        # Test OpenWeatherMap API
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': city,
            'appid': api_key,
            'units': 'metric'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return JsonResponse({
                        'success': True,
                        'api_key_valid': True,
                        'data': {
                            'city': data['name'],
                            'country': data['sys']['country'],
                            'temperature': data['main']['temp'],
                            'description': data['weather'][0]['description'],
                            'humidity': data['main']['humidity']
                        }
                    })
                elif response.status == 401:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid API key',
                        'api_key_valid': False,
                        'status_code': response.status
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': f'API error: {response.status}',
                        'api_key_valid': True,
                        'status_code': response.status
                    })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'api_key_valid': True
        })
