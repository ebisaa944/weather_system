"""
Utility to check environment variables and API configuration
"""
import os
from django.conf import settings

def check_env_variables():
    """Check if all required environment variables are set"""
    required_vars = [
        'SECRET_KEY',
        'OPENWEATHER_API_KEY',
        'WEATHER_API_KEY',
    ]
    
    optional_vars = [
        'WEATHERAPI_KEY',
        'MAPBOX_TOKEN',
        'REDIS_URL',
        'EMAIL_HOST_USER',
        'EMAIL_HOST_PASSWORD',
        'DATABASE_URL',
    ]
    
    results = {
        'required': {},
        'optional': {},
        'status': 'OK'
    }
    
    # Check required variables
    for var in required_vars:
        value = os.getenv(var)
        if value and value not in ['', 'your-actual-openweather-api-key-here', 'your-super-secret-key-change-this-in-production']:
            results['required'][var] = '✓ Set'
        else:
            results['required'][var] = '✗ Missing or using default'
            results['status'] = 'WARNING'
    
    # Check optional variables
    for var in optional_vars:
        value = os.getenv(var)
        if value and value not in ['', 'your-email@gmail.com', 'your-app-password']:
            results['optional'][var] = '✓ Set'
        else:
            results['optional'][var] = '○ Not set (optional)'
    
    return results

def get_weather_api_config():
    """Get weather API configuration from environment"""
    return {
        'primary': {
            'name': 'OpenWeatherMap',
            'api_key': os.getenv('OPENWEATHER_API_KEY', os.getenv('WEATHER_API_KEY', '')),
            'url': os.getenv('WEATHER_API_URL', 'https://api.openweathermap.org/data/2.5'),
            'timeout': 10,
            'retries': 3,
        },
        'secondary': {
            'name': 'WeatherAPI',
            'api_key': os.getenv('WEATHERAPI_KEY', ''),
            'url': 'http://api.weatherapi.com/v1',
            'timeout': 10,
            'retries': 2,
        },
        'fallback': {
            'name': 'OpenMeteo',
            'url': 'https://api.open-meteo.com/v1',
            'timeout': 15,
            'retries': 2,
        }
    }

def get_system_info():
    """Get system information for debugging"""
    import platform
    import django
    from datetime import datetime
    
    return {
        'system': platform.system(),
        'python_version': platform.python_version(),
        'django_version': django.get_version(),
        'debug_mode': settings.DEBUG,
        'database': 'SQLite' if 'sqlite' in str(settings.DATABASES['default']['ENGINE']) else 'Other',
        'cache_backend': settings.CACHES['default']['BACKEND'].split('.')[-2] + '.' + settings.CACHES['default']['BACKEND'].split('.')[-1],
        'timezone': settings.TIME_ZONE,
        'server_time': datetime.now().isoformat(),
    }

def mask_api_key(api_key: str) -> str:
    """Mask API key for display"""
    if not api_key:
        return 'Not set'
    if len(api_key) <= 8:
        return '*' * len(api_key)
    return api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]

def get_safe_api_config():
    """Get API configuration with masked keys for display"""
    config = get_weather_api_config()
    for key in config:
        if 'api_key' in config[key]:
            config[key]['api_key'] = mask_api_key(config[key]['api_key'])
    return config

def check_redis_connection():
    """Check if Redis is available and connected"""
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1')
        client = redis.from_url(redis_url)
        client.ping()
        return {'status': 'connected', 'url': redis_url}
    except ImportError:
        return {'status': 'redis package not installed', 'url': None}
    except Exception as e:
        return {'status': f'error: {str(e)}', 'url': redis_url}

def get_all_env_info():
    """Get all environment information for debugging"""
    return {
        'environment_variables': check_env_variables(),
        'api_configuration': get_safe_api_config(),
        'system_info': get_system_info(),
        'redis': check_redis_connection(),
        'installed_apps': settings.INSTALLED_APPS,
    }