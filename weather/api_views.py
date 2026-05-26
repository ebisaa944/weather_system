"""
Mobile-optimized API endpoints
"""
import asyncio
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import UserProfile, Notification, FavoriteCity, SearchHistory
from .serializers import (
    MobileUserSerializer,
    MobileFavoriteSerializer,
    MobileNotificationSerializer,
    MobileWeatherSerializer
)
from .weather_service_advanced import AdvancedWeatherService

weather_service = AdvancedWeatherService()


def run_async(coro):
    """Run async helpers safely from sync DRF views."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        return asyncio.run(coro)
    return loop.run_until_complete(coro)

@api_view(['POST'])
def mobile_login(request):
    """Mobile-optimized login endpoint"""
    # JWT token generation for mobile
    from rest_framework_simplejwt.tokens import RefreshToken
    
    username = request.data.get('username')
    password = request.data.get('password')
    
    from django.contrib.auth import authenticate
    user = authenticate(username=username, password=password)
    
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'success': True,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': MobileUserSerializer(user).data
        })
    else:
        return Response({
            'success': False,
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
def mobile_register(request):
    """Mobile user registration"""
    from django.contrib.auth.models import User
    
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    
    if User.objects.filter(username=username).exists():
        return Response({
            'success': False,
            'error': 'Username already exists'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )
    
    # Create profile
    UserProfile.objects.create(user=user)
    
    return Response({
        'success': True,
        'message': 'User created successfully'
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mobile_dashboard(request):
    """Mobile dashboard with all user data"""
    user = request.user
    
    # Get favorites with weather
    favorites = FavoriteCity.objects.filter(user=user, is_active=True)
    favorite_data = []
    
    for favorite in favorites:
        weather = run_async(weather_service.fetch_weather_multiple_sources(favorite.city_name))
        favorite_data.append({
            'favorite': MobileFavoriteSerializer(favorite).data,
            'weather': MobileWeatherSerializer(weather).data if weather else None
        })
        
    # Get recent searches
    recent = SearchHistory.objects.filter(user=user)[:10]
    
    # Get unread notifications
    notifications = Notification.objects.filter(user=user, is_read=False)[:5]
    
    return Response({
        'success': True,
        'user': MobileUserSerializer(user).data,
        'favorites': favorite_data,
        'recent_searches': [
            {
                'city_name': item.city_name,
                'country': item.country,
                'search_date': item.search_date,
            }
            for item in recent
        ],
        'notifications': MobileNotificationSerializer(notifications, many=True).data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mobile_weather(request):
    """Mobile weather endpoint with caching"""
    city = request.GET.get('city')
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    user = request.user
    
    if city:
        weather = run_async(weather_service.fetch_weather_multiple_sources(city))
    elif lat and lon:
        # Reverse geocode to get city
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="weather_mobile")
        location = geolocator.reverse(f"{lat}, {lon}")
        if location:
            city = location.address.split(',')[0]
            weather = run_async(weather_service.fetch_weather_multiple_sources(city))
        else:
            return Response({
                'success': False,
                'error': 'Location not found'
            }, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({
            'success': False,
            'error': 'City or coordinates required'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    # Save search if authenticated
    if user.is_authenticated:
        SearchHistory.objects.create(
            user=user,
            city_name=city
        )
        
    return Response({
        'success': True,
        'data': MobileWeatherSerializer(weather).data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mobile_favorite(request):
    """Add/remove favorite from mobile"""
    user = request.user
    city = request.data.get('city')
    action = request.data.get('action', 'add')
    
    if not city:
        return Response({
            'success': False,
            'error': 'City required'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    if action == 'add':
        favorite, created = FavoriteCity.objects.get_or_create(
            user=user,
            city_name=city
        )
        if not created:
            favorite.is_active = True
            favorite.save()
            
        return Response({
            'success': True,
            'message': f'{city} added to favorites'
        })
        
    elif action == 'remove':
        FavoriteCity.objects.filter(
            user=user,
            city_name=city
        ).update(is_active=False)
        
        return Response({
            'success': True,
            'message': f'{city} removed from favorites'
        })

    return Response({
        'success': False,
        'error': 'Invalid action'
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mobile_notifications(request):
    """Get user notifications for mobile"""
    user = request.user
    
    # Mark notifications as delivered
    notifications = Notification.objects.filter(
        user=user,
        is_sent=False
    ).order_by('-created_at')[:20]
    
    for notification in notifications:
        notification.is_sent = True
        notification.sent_at = timezone.now()
        notification.save()
        
    serializer = MobileNotificationSerializer(notifications, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mobile_device_token(request):
    """Register device token for push notifications"""
    user = request.user
    token = request.data.get('token')
    device_type = request.data.get('device_type', 'android')
    
    if not token:
        return Response({
            'success': False,
            'error': 'Token required'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.fcm_token = token
    profile.device_type = device_type
    profile.save()
    
    return Response({
        'success': True,
        'message': 'Device registered successfully'
    })
