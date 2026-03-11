"""
Root URL configuration for weather_system project.
Includes web interfaces, API endpoints, and documentation.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, HttpResponse
from django.views.generic import TemplateView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from axes.decorators import axes_dispatch
from weather import urls as weather_urls

# API Schema View for Swagger documentation
schema_view = get_schema_view(
    openapi.Info(
        title="Weather System API",
        default_version='v2.0',
        description="Enterprise-Grade Weather Data API with Multiple Sources",
        terms_of_service="https://www.weathersystem.com/terms/",
        contact=openapi.Contact(email="api@weathersystem.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[],
)

def health_check(request):
    """Enhanced health check endpoint for monitoring"""
    import datetime
    import socket
    from django.db import connection
    from django.core.cache import cache
    
    # Check database connection
    db_status = 'healthy'
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    
    # Check cache connection
    cache_status = 'healthy'
    try:
        cache.set('health_check', 'ok', 5)
        cache.get('health_check')
    except Exception as e:
        cache_status = f'unhealthy: {str(e)}'
    
    return JsonResponse({
        'status': 'healthy' if db_status == 'healthy' and cache_status == 'healthy' else 'degraded',
        'service': 'Weather System',
        'version': '2.0.0',
        'hostname': socket.gethostname(),
        'timestamp': datetime.datetime.now().isoformat(),
        'checks': {
            'database': db_status,
            'cache': cache_status,
            'apis': {
                'openweather': 'configured' if settings.WEATHER_API.get('primary', {}).get('api_key') else 'missing',
                'weatherapi': 'configured' if settings.WEATHER_API.get('secondary', {}).get('api_key') else 'optional',
                'openmeteo': 'available'
            }
        },
        'features': [
            'current_weather',
            'forecast_5day',
            'hourly_forecast',
            'air_quality',
            'weather_maps',
            'alerts',
            'historical_data',
            'weather_statistics',
            'multi_city_comparison',
            'geocoding',
            'reverse_geocoding'
        ]
    })

def api_root(request):
    """API v2 root endpoint with available endpoints"""
    base_url = request.build_absolute_uri('/api/v2/')
    
    return JsonResponse({
        'name': 'Weather System API',
        'version': '2.0',
        'documentation': request.build_absolute_uri('/api/docs/'),
        'endpoints': {
            'weather': {
                'current': f'{base_url}weather/current/?city={{city_name}}',
                'by_coordinates': f'{base_url}weather/current/coords/?lat={{lat}}&lon={{lon}}',
                'multiple_cities': f'{base_url}weather/current/multiple/?cities[]=London&cities[]=Tokyo',
                'forecast': f'{base_url}weather/forecast/?city={{city_name}}&days=5',
                'hourly': f'{base_url}weather/forecast/hourly/?city={{city_name}}&hours=24',
            },
            'air_quality': {
                'current': f'{base_url}weather/air-quality/?lat={{lat}}&lon={{lon}}',
                'history': f'{base_url}weather/air-quality/history/?city={{city_name}}&days=7',
            },
            'search': {
                'cities': f'{base_url}weather/search/?q={{query}}',
                'geocode': f'{base_url}weather/geocode/?location={{city_name}}',
                'reverse_geocode': f'{base_url}weather/reverse-geocode/?lat={{lat}}&lon={{lon}}',
            },
            'historical': {
                'data': f'{base_url}weather/historical/?city={{city_name}}&days=7',
                'statistics': f'{base_url}weather/statistics/?city={{city_name}}',
            },
            'alerts': {
                'active': f'{base_url}weather/alerts/?city={{city_name}}',
                'subscribe': f'{base_url}weather/alerts/subscribe/',
            },
            'user': {
                'favorites': f'{base_url}user/favorites/',
                'settings': f'{base_url}user/settings/',
            }
        },
        'rate_limits': {
            'anonymous': '100 requests per day',
            'authenticated': '1000 requests per day',
            'premium': 'Custom limits available'
        }
    })

def robots_txt(request):
    """Robots.txt for SEO"""
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Allow: /",
        "Sitemap: https://weathersystem.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def sitemap_xml(request):
    """Sitemap for SEO"""
    urls = [
        {"loc": "https://weathersystem.com/", "priority": "1.0"},
        {"loc": "https://weathersystem.com/dashboard/", "priority": "0.8"},
        {"loc": "https://weathersystem.com/map/", "priority": "0.7"},
        {"loc": "https://weathersystem.com/alerts/", "priority": "0.7"},
    ]
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for url in urls:
        xml += '  <url>\n'
        xml += f'    <loc>{url["loc"]}</loc>\n'
        xml += f'    <priority>{url["priority"]}</priority>\n'
        xml += '  </url>\n'
    
    xml += '</urlset>'
    
    return HttpResponse(xml, content_type="application/xml")

# Main URL patterns
urlpatterns = [
    # Admin interface (protected by axes)
    path('admin/', axes_dispatch(admin.site.urls), name='admin'),
    
    # Health check (for monitoring)
    path('health/', health_check, name='health_check'),
    
    # SEO endpoints
    path('robots.txt', robots_txt, name='robots'),
    path('sitemap.xml', sitemap_xml, name='sitemap'),
    
    # Web interface - main weather app
    path('', include('weather.urls', namespace='weather')),
    
    # API v2 endpoints
    path('api/v2/', api_root, name='api_root'),
    path('api/v2/', include('weather.urls', namespace='api_v2')),
    
    # API v1 endpoints (backward compatibility)
    path('api/v1/', include((weather_urls.api_v2_patterns, 'weather'), namespace='api_v1')),
    
    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/json/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
    # Authentication
    path('accounts/', include('allauth.urls')),
    
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include('debug_toolbar.urls')),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Add debug endpoint to list all URLs
    from django.urls import get_resolver
    
    def debug_urls(request):
        """Debug view to show all registered URLs"""
        resolver = get_resolver()
        url_list = []
        
        def collect_urls(pattern, prefix=''):
            if hasattr(pattern, 'url_patterns'):
                for p in pattern.url_patterns:
                    collect_urls(p, prefix + str(pattern.pattern))
            else:
                url_list.append({
                    'pattern': str(pattern.pattern),
                    'name': pattern.name,
                    'route': prefix + str(pattern.pattern),
                    'callback': str(pattern.callback)
                })
        
        collect_urls(resolver)
        
        return JsonResponse({
            'total_urls': len(url_list),
            'urls': sorted(url_list, key=lambda x: x['pattern'])
        }, json_dumps_params={'indent': 2})
    
    urlpatterns += [
        path('debug/urls/', debug_urls, name='debug_urls'),
    ]
