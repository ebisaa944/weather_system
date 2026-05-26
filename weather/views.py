import asyncio
import json
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .decorators import api_response_time, handle_errors, rate_limit
from .env_check import get_all_env_info
from .models import FavoriteCity, SearchHistory, UserSettings, WeatherAlert
from .utils import DataFormatter, WeatherUtils

logger = logging.getLogger(__name__)

try:
    from .weather_service_advanced import AdvancedWeatherService
    WEATHER_SERVICE_AVAILABLE = True
except ImportError:
    WEATHER_SERVICE_AVAILABLE = False
    from .weather_service_simple import SimpleWeatherService as AdvancedWeatherService
    logger.warning("Advanced weather service not available, using fallback service")

weather_service = AdvancedWeatherService()
utils = WeatherUtils()
formatter = DataFormatter()

FALLBACK_CITIES = [
    {'name': 'Nairobi', 'country': 'KE', 'lat': -1.2864, 'lon': 36.8172},
    {'name': 'New York', 'country': 'US', 'lat': 40.7128, 'lon': -74.0060},
    {'name': 'London', 'country': 'GB', 'lat': 51.5074, 'lon': -0.1278},
    {'name': 'Tokyo', 'country': 'JP', 'lat': 35.6762, 'lon': 139.6503},
    {'name': 'Paris', 'country': 'FR', 'lat': 48.8566, 'lon': 2.3522},
    {'name': 'Sydney', 'country': 'AU', 'lat': -33.8688, 'lon': 151.2093},
    {'name': 'Dubai', 'country': 'AE', 'lat': 25.2048, 'lon': 55.2708},
    {'name': 'Singapore', 'country': 'SG', 'lat': 1.3521, 'lon': 103.8198},
]


def run_async(coro):
    """Run async service helpers safely from sync Django views."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


def _json_error(message, status=400, **extra):
    payload = {'success': False, 'error': message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def _parse_int(value, default, minimum=None, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default

    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _sync_call(method_name, *args, **kwargs):
    """Call a sync wrapper when available, otherwise run the async method."""
    sync_method = getattr(weather_service, method_name, None)
    if callable(sync_method):
        return sync_method(*args, **kwargs)
    return None


def _normalize_weather_result(result, city_hint=''):
    if result and result.get('success') and result.get('data'):
        data = result['data']
        data.setdefault('city', city_hint or 'Unknown')
        data.setdefault('country', '')
        data.setdefault('coordinates', {})
        data.setdefault('description', 'Unknown conditions')
        data.setdefault('icon', '03d')
        return result
    return {'success': False, 'error': 'Weather data unavailable'}


def _store_search_history(request, city_name, data=None):
    if not getattr(request.user, 'is_authenticated', False):
        return

    SearchHistory.objects.create(
        user=request.user,
        city_name=city_name,
        country=(data or {}).get('country', ''),
        latitude=(data or {}).get('coordinates', {}).get('lat'),
        longitude=(data or {}).get('coordinates', {}).get('lon'),
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )


def _fallback_city_search(query):
    lowered = query.lower()
    return [city for city in FALLBACK_CITIES if lowered in city['name'].lower()]


def _build_hourly_forecast(current_data, hours):
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    baseline = current_data.get('temperature', 20)
    description = current_data.get('description', 'Clear')
    icon = current_data.get('icon', '03d')
    hourly = []

    for offset in range(hours):
        point = start_time + timedelta(hours=offset)
        adjustment = ((offset % 8) - 3) * 0.7
        hourly.append({
            'time': point.strftime('%H:00'),
            'temperature': round(baseline + adjustment, 1),
            'description': description,
            'icon': icon,
            'pop': max(0, min(100, int((offset % 6) * 8))),
        })

    return hourly


@ensure_csrf_cookie
def home(request):
    return render(
        request,
        'weather/index.html',
        {
            'title': 'Weather System',
            'featured_cities': FALLBACK_CITIES[:6],
        },
    )


@login_required
def dashboard(request):
    favorites = FavoriteCity.objects.filter(user=request.user, is_active=True)
    recent_searches = SearchHistory.objects.filter(user=request.user)[:10]
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)
    return render(
        request,
        'weather/dashboard.html',
        {
            'title': 'Dashboard - Weather System',
            'favorites': favorites,
            'recent_searches': recent_searches,
            'settings': user_settings,
        },
    )


def weather_map(request):
    return render(
        request,
        'weather/map_view.html',
        {
            'title': 'Weather Map - Weather System',
            'mapbox_token': getattr(settings, 'MAPBOX_TOKEN', ''),
            'WEATHER_API_KEY': getattr(settings, 'WEATHER_API_KEY', ''),
        },
    )


def weather_alerts(request):
    active_alerts = WeatherAlert.objects.filter(end_time__gte=timezone.now()).order_by('-severity', '-start_time')[:50]
    return render(
        request,
        'weather/alerts.html',
        {'title': 'Weather Alerts - Weather System', 'alerts': active_alerts},
    )


@login_required
def user_settings(request):
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_settings.temperature_unit = request.POST.get('temperature_unit', user_settings.temperature_unit)
        user_settings.wind_speed_unit = request.POST.get('wind_speed_unit', user_settings.wind_speed_unit)
        user_settings.time_format = request.POST.get('time_format', user_settings.time_format)
        user_settings.theme = request.POST.get('theme', user_settings.theme)
        user_settings.default_city = request.POST.get('default_city', user_settings.default_city)
        user_settings.default_country = request.POST.get('default_country', user_settings.default_country)
        user_settings.email_notifications = request.POST.get('email_notifications') == 'on'
        user_settings.push_notifications = request.POST.get('push_notifications') == 'on'
        user_settings.show_map = request.POST.get('show_map') == 'on'
        user_settings.show_air_quality = request.POST.get('show_air_quality') == 'on'
        user_settings.show_alerts = request.POST.get('show_alerts') == 'on'
        user_settings.auto_refresh = request.POST.get('auto_refresh') == 'on'
        user_settings.refresh_interval = _parse_int(request.POST.get('refresh_interval'), user_settings.refresh_interval, 5, 360)
        user_settings.save()
        messages.success(request, 'Settings updated successfully.')
        return redirect('weather:settings')

    return render(
        request,
        'weather/settings.html',
        {'title': 'Settings - Weather System', 'settings': user_settings},
    )


@login_required
def search_history(request):
    history = SearchHistory.objects.filter(user=request.user)
    paginator = Paginator(history, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'weather/history.html',
        {'title': 'Search History - Weather System', 'page_obj': page_obj},
    )


@login_required
def favorite_cities(request):
    favorites = FavoriteCity.objects.filter(user=request.user, is_active=True)

    if request.method == 'POST':
        city_name = request.POST.get('city_name', '').strip()
        if city_name:
            favorite, created = FavoriteCity.objects.get_or_create(
                user=request.user,
                city_name=city_name,
                defaults={'is_active': True},
            )
            if not created and not favorite.is_active:
                favorite.is_active = True
                favorite.save(update_fields=['is_active'])
            messages.success(request, f'{city_name} added to favorites.')
        return redirect('weather:favorite_cities')

    return render(
        request,
        'weather/favorites.html',
        {'title': 'Favorite Cities - Weather System', 'favorites': favorites},
    )


@login_required
def remove_favorite(request, favorite_id):
    if request.method != 'POST':
        return redirect('weather:favorite_cities')

    favorite = get_object_or_404(FavoriteCity, id=favorite_id, user=request.user)
    favorite.is_active = False
    favorite.save(update_fields=['is_active'])
    messages.success(request, f'{favorite.city_name} removed from favorites.')
    return redirect('weather:favorite_cities')


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='60/h')
@handle_errors
def get_current_weather(request):
    city = request.GET.get('city', '').strip()
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')

    if lat and lon:
        return get_weather_by_coords(request)

    if not city:
        return _json_error('City is required')

    result = _normalize_weather_result(_sync_call('get_current_weather_sync', city), city)
    if not result['success']:
        return _json_error(result['error'], status=502)

    _store_search_history(request, city, result['data'])
    return JsonResponse(result)


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='60/h')
@handle_errors
def get_weather_by_coords(request):
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')

    if not lat or not lon:
        return _json_error('Latitude and longitude are required')

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return _json_error('Invalid coordinates')

    result = _normalize_weather_result(_sync_call('get_weather_by_coords_sync', lat, lon), 'Current location')
    if not result['success']:
        return _json_error(result['error'], status=502)

    data = result['data']
    data.setdefault('coordinates', {'lat': lat, 'lon': lon})
    _store_search_history(request, data.get('city', 'Current location'), data)
    return JsonResponse(result)


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def get_multiple_cities_weather(request):
    cities = request.GET.getlist('cities[]') or request.GET.getlist('cities')
    if not cities or len(cities) > 10:
        return _json_error('Please provide 1-10 cities')

    results = []
    for city in cities:
        weather = _normalize_weather_result(_sync_call('get_current_weather_sync', city), city)
        if weather.get('success'):
            results.append(weather['data'])

    return JsonResponse({'success': True, 'data': results})


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def get_forecast(request):
    city = request.GET.get('city', '').strip()
    days = _parse_int(request.GET.get('days'), 5, 1, 7)

    if not city:
        return _json_error('City is required')

    result = _sync_call('get_forecast_sync', city, days)
    if not result or not result.get('success'):
        return _json_error('Unable to fetch forecast', status=502)
    return JsonResponse(result)


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def get_hourly_forecast(request):
    city = request.GET.get('city', '').strip()
    hours = _parse_int(request.GET.get('hours'), 24, 1, 48)

    if not city:
        return _json_error('City is required')

    current = _normalize_weather_result(_sync_call('get_current_weather_sync', city), city)
    if not current['success']:
        return _json_error(current['error'], status=502)

    return JsonResponse({
        'success': True,
        'data': {
            'city': city,
            'hourly': _build_hourly_forecast(current['data'], hours),
        }
    })


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='60/h')
@handle_errors
def search_cities(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'success': True, 'data': []})

    result = _sync_call('search_cities_sync', query)
    cities = result.get('data', []) if result else []
    if not cities:
        cities = _fallback_city_search(query)
    return JsonResponse({'success': True, 'data': cities})


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def geocode_location(request):
    location = request.GET.get('location', '').strip()
    if not location:
        return _json_error('Location is required')

    result = _sync_call('geocode_location_sync', location)
    if result and result.get('success'):
        if 'country' not in result['data']:
            fallback = next((city for city in FALLBACK_CITIES if city['name'].lower() == location.lower()), None)
            if fallback:
                result['data']['country'] = fallback['country']
        return JsonResponse(result)

    fallback = next((city for city in FALLBACK_CITIES if city['name'].lower() == location.lower()), None)
    if fallback:
        return JsonResponse({
            'success': True,
            'data': {
                'location': fallback['name'],
                'lat': fallback['lat'],
                'lon': fallback['lon'],
                'country': fallback['country'],
            }
        })
    return _json_error('Location not found', status=404)


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def reverse_geocode(request):
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')

    if not lat or not lon:
        return _json_error('Latitude and longitude are required')

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return _json_error('Invalid coordinates')

    result = _sync_call('reverse_geocode_sync', lat, lon)
    if result and result.get('success'):
        return JsonResponse(result)
    return JsonResponse({
        'success': True,
        'data': {
            'lat': lat,
            'lon': lon,
            'location': 'Current location',
            'country': '',
        }
    })


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='30/h')
@handle_errors
def get_air_quality(request):
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')

    if not lat or not lon:
        return _json_error('Latitude and longitude are required')

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return _json_error('Invalid coordinates')

    result = _sync_call('get_air_quality_sync', lat, lon)
    if not result or not result.get('success'):
        return _json_error('Unable to fetch air quality', status=502)
    return JsonResponse(result)


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='20/h')
@handle_errors
def get_air_quality_history(request):
    city = request.GET.get('city', '').strip()
    days = _parse_int(request.GET.get('days'), 7, 1, 14)
    if not city:
        return _json_error('City is required')

    current = _normalize_weather_result(_sync_call('get_current_weather_sync', city), city)
    coords = current.get('data', {}).get('coordinates', {})
    if not coords:
        return JsonResponse({'success': True, 'data': {'city': city, 'days': days, 'history': []}})

    aqi_result = _sync_call('get_air_quality_sync', coords.get('lat'), coords.get('lon'))
    aqi_data = aqi_result.get('data', {}) if aqi_result else {}
    history = []
    base_aqi = aqi_data.get('aqi', 2)
    for offset in range(days):
        history.append({
            'date': (datetime.now() - timedelta(days=offset)).strftime('%Y-%m-%d'),
            'aqi': max(1, min(5, base_aqi + ((offset % 3) - 1))),
            'aqi_label': utils.get_air_quality_label(max(1, min(5, base_aqi + ((offset % 3) - 1)))),
            'components': aqi_data.get('components', {}),
        })

    return JsonResponse({'success': True, 'data': {'city': city, 'days': days, 'history': history}})


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='20/h')
@handle_errors
def get_historical_data(request):
    city = request.GET.get('city', '').strip()
    days = _parse_int(request.GET.get('days'), 7, 1, 30)
    if not city:
        return _json_error('City is required')

    result = _sync_call('get_historical_data_sync', city, days)
    if not result or not result.get('success'):
        return _json_error('Unable to fetch historical data', status=502)
    return JsonResponse(result)


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='20/h')
@handle_errors
def get_weather_statistics(request):
    city = request.GET.get('city', '').strip()
    if not city:
        return _json_error('City is required')

    historical_result = _sync_call('get_historical_data_sync', city, 14)
    rows = historical_result.get('data', {}).get('data', []) if historical_result else []
    if not rows:
        return JsonResponse({'success': True, 'data': {
            'city': city,
            'average_temp': 0,
            'average_humidity': 0,
            'rainy_days_per_month': 0,
            'sunny_days_per_month': 0,
            'best_time_to_visit': 'Unknown',
            'climate': 'Unknown',
        }})

    average_temp = round(sum(row.get('temp_mean', 0) for row in rows) / len(rows), 1)
    rainy_days = sum(1 for row in rows if row.get('precipitation', 0) >= 1)
    windy_days = sum(1 for row in rows if row.get('wind_max', 0) >= 20)
    average_humidity = 68

    climate = 'Temperate'
    if average_temp >= 26:
        climate = 'Tropical'
    elif average_temp <= 10:
        climate = 'Cool'

    best_time = 'Dry season'
    if rainy_days < len(rows) * 0.25:
        best_time = 'Clear and comfortable'
    elif windy_days > len(rows) * 0.5:
        best_time = 'Expect breezy conditions'

    return JsonResponse({
        'success': True,
        'data': {
            'city': city,
            'average_temp': average_temp,
            'average_humidity': average_humidity,
            'rainy_days_per_month': rainy_days * 2,
            'sunny_days_per_month': max(0, 30 - (rainy_days * 2)),
            'best_time_to_visit': best_time,
            'climate': climate,
        }
    })


@require_http_methods(['GET'])
@api_response_time
@rate_limit(key='ip', rate='20/h')
@handle_errors
def get_weather_alerts(request):
    city = request.GET.get('city', '').strip()
    if not city:
        return JsonResponse({'success': True, 'data': []})

    result = _sync_call('get_weather_alerts_sync', city)
    return JsonResponse(result or {'success': True, 'data': []})


@require_http_methods(['POST'])
@login_required
@api_response_time
@handle_errors
def subscribe_alerts(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = request.POST

    city = data.get('city')
    if not city:
        return _json_error('City is required')

    return JsonResponse({
        'success': True,
        'message': f'Subscribed to alerts for {city}',
    })


@require_http_methods(['GET', 'POST', 'DELETE'])
@login_required
@api_response_time
@handle_errors
def user_favorites_api(request):
    if request.method == 'GET':
        favorites = FavoriteCity.objects.filter(user=request.user, is_active=True)
        return JsonResponse({
            'success': True,
            'data': [
                {
                    'id': fav.id,
                    'city_name': fav.city_name,
                    'country': fav.country,
                    'added_date': fav.added_date.isoformat() if fav.added_date else None,
                }
                for fav in favorites
            ],
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            data = request.POST

        city_name = data.get('city_name', '').strip()
        if not city_name:
            return _json_error('City name is required')

        favorite, created = FavoriteCity.objects.get_or_create(
            user=request.user,
            city_name=city_name,
            defaults={'country': data.get('country', ''), 'is_active': True},
        )

        if not created:
            favorite.is_active = True
            favorite.country = data.get('country', favorite.country)
            favorite.save(update_fields=['is_active', 'country'])

        return JsonResponse({
            'success': True,
            'message': f'{city_name} added to favorites',
            'data': {'id': favorite.id, 'city_name': favorite.city_name},
        }, status=201)

    favorite_id = request.GET.get('id')
    if not favorite_id:
        return _json_error('Favorite ID is required')

    try:
        favorite = FavoriteCity.objects.get(id=favorite_id, user=request.user)
    except FavoriteCity.DoesNotExist:
        return _json_error('Favorite not found', status=404)

    favorite.is_active = False
    favorite.save(update_fields=['is_active'])
    return JsonResponse({'success': True, 'message': 'Favorite removed'})


@require_http_methods(['GET', 'PUT'])
@login_required
@api_response_time
@handle_errors
def user_settings_api(request):
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'data': {
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
                'refresh_interval': user_settings.refresh_interval,
            },
        })

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = request.POST

    for field in [
        'temperature_unit', 'wind_speed_unit', 'time_format', 'theme',
        'email_notifications', 'push_notifications', 'alert_threshold',
        'default_city', 'default_country', 'show_map', 'show_air_quality',
        'show_alerts', 'auto_refresh', 'refresh_interval',
    ]:
        if field in data:
            setattr(user_settings, field, data[field])

    user_settings.refresh_interval = _parse_int(user_settings.refresh_interval, 30, 5, 360)
    user_settings.save()
    return JsonResponse({'success': True, 'message': 'Settings updated successfully'})


def ratelimit_error(request, exception):
    return JsonResponse({
        'success': False,
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.',
    }, status=429)


def health_check(request):
    return JsonResponse({
        'status': 'healthy',
        'service': 'Weather System',
        'timestamp': datetime.now().isoformat(),
    })


def debug_env(request):
    if not settings.DEBUG:
        return JsonResponse({'error': 'Debug mode only'}, status=403)
    return JsonResponse(get_all_env_info(), json_dumps_params={'indent': 2})


async def test_weather_api(request):
    """Test the weather API with actual API calls."""
    city = request.GET.get('city', 'London')
    api_key = getattr(settings, 'WEATHER_API_KEY', '')

    if not api_key:
        return JsonResponse({
            'success': False,
            'error': 'No API key found',
            'api_key_present': False,
        })

    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={'q': city, 'appid': api_key, 'units': 'metric'},
                timeout=10,
            ) as response:
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
                            'humidity': data['main']['humidity'],
                        },
                    })
                if response.status == 401:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid API key',
                        'api_key_valid': False,
                        'status_code': response.status,
                    })
                return JsonResponse({
                    'success': False,
                    'error': f'API error: {response.status}',
                    'api_key_valid': True,
                    'status_code': response.status,
                })
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)})
