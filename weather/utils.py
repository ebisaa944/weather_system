import hashlib
import json
import logging
import requests
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional, List
import re

logger = logging.getLogger(__name__)

class WeatherUtils:
    """Utility functions for weather system"""
    
    @staticmethod
    def generate_cache_key(prefix: str, **kwargs) -> str:
        """Generate cache key from parameters"""
        key_string = f"{prefix}_{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    @staticmethod
    def celsius_to_fahrenheit(celsius: float) -> float:
        """Convert Celsius to Fahrenheit"""
        return (celsius * 9/5) + 32
    
    @staticmethod
    def fahrenheit_to_celsius(fahrenheit: float) -> float:
        """Convert Fahrenheit to Celsius"""
        return (fahrenheit - 32) * 5/9
    
    @staticmethod
    def ms_to_mph(ms: float) -> float:
        """Convert meters per second to miles per hour"""
        return ms * 2.23694
    
    @staticmethod
    def mph_to_ms(mph: float) -> float:
        """Convert miles per hour to meters per second"""
        return mph / 2.23694
    
    @staticmethod
    def get_wind_direction(degrees: float) -> str:
        """Convert wind degrees to cardinal direction"""
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                     'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        index = round(degrees / (360 / len(directions))) % len(directions)
        return directions[index]
    
    @staticmethod
    def get_air_quality_label(aqi: int) -> str:
        """Convert AQI number to label"""
        labels = {
            1: 'Good',
            2: 'Fair',
            3: 'Moderate',
            4: 'Poor',
            5: 'Very Poor'
        }
        return labels.get(aqi, 'Unknown')
    
    @staticmethod
    def get_air_quality_color(aqi: int) -> str:
        """Get color for AQI"""
        colors = {
            1: '#00e400',  # Green
            2: '#ffff00',  # Yellow
            3: '#ff7e00',  # Orange
            4: '#ff0000',  # Red
            5: '#8f3f97'   # Purple
        }
        return colors.get(aqi, '#808080')
    
    @staticmethod
    def validate_city_name(city: str) -> bool:
        """Validate city name format"""
        if not city or len(city) < 2:
            return False
        # Allow letters, spaces, hyphens, and dots
        pattern = r'^[a-zA-Z\s\-\.]+$'
        return bool(re.match(pattern, city))
    
    @staticmethod
    def format_time(timestamp: int, time_format: str = '24h') -> str:
        """Format timestamp according to user preference"""
        dt = datetime.fromtimestamp(timestamp)
        if time_format == '12h':
            return dt.strftime('%I:%M %p')
        return dt.strftime('%H:%M')
    
    @staticmethod
    def get_weather_icon_url(icon_code: str, size: str = '2x') -> str:
        """Get OpenWeatherMap icon URL"""
        base_url = "https://openweathermap.org/img/wn/"
        return f"{base_url}{icon_code}@{size}.png"
    
    @staticmethod
    def calculate_dew_point(temp: float, humidity: float) -> float:
        """Calculate dew point temperature"""
        a = 17.27
        b = 237.7
        alpha = ((a * temp) / (b + temp)) + (humidity / 100)
        return (b * alpha) / (a - alpha)
    
    @staticmethod
    def get_thermal_sensation(temp: float, wind_speed: float, humidity: float) -> Dict[str, Any]:
        """Calculate thermal sensation (wind chill, heat index)"""
        if temp <= 10 and wind_speed > 1.34:
            # Wind chill calculation (for cold conditions)
            wind_chill = 13.12 + 0.6215 * temp - 11.37 * (wind_speed ** 0.16) + 0.3965 * temp * (wind_speed ** 0.16)
            return {'type': 'wind_chill', 'value': round(wind_chill, 1)}
        elif temp >= 27:
            # Heat index calculation (for hot conditions)
            heat_index = -8.784695 + 1.61139411 * temp + 2.338549 * humidity - 0.14611605 * temp * humidity
            heat_index += -0.012308094 * temp**2 - 0.016424828 * humidity**2 + 0.002211732 * temp**2 * humidity
            heat_index += 0.00072546 * temp * humidity**2 - 0.000003582 * temp**2 * humidity**2
            return {'type': 'heat_index', 'value': round(heat_index, 1)}
        else:
            return {'type': 'normal', 'value': temp}
    
    @staticmethod
    def get_uv_index_risk(uv: float) -> Dict[str, Any]:
        """Get UV index risk level"""
        if uv < 3:
            return {'level': 'Low', 'color': 'green', 'protection': 'No protection required'}
        elif uv < 6:
            return {'level': 'Moderate', 'color': 'yellow', 'protection': 'Wear sunscreen'}
        elif uv < 8:
            return {'level': 'High', 'color': 'orange', 'protection': 'Sun protection required'}
        elif uv < 11:
            return {'level': 'Very High', 'color': 'red', 'protection': 'Extra protection required'}
        else:
            return {'level': 'Extreme', 'color': 'purple', 'protection': 'Avoid sun exposure'}

class CacheManager:
    """Manage caching for weather data"""
    
    def __init__(self):
        self.default_timeout = 600  # 10 minutes
    
    def get(self, key: str):
        """Get value from cache"""
        return cache.get(key)
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None):
        """Set value in cache"""
        if timeout is None:
            timeout = self.default_timeout
        cache.set(key, value, timeout)
    
    def delete(self, key: str):
        """Delete value from cache"""
        cache.delete(key)
    
    def get_or_set(self, key: str, func, timeout: Optional[int] = None):
        """Get from cache or set using function"""
        value = self.get(key)
        if value is None:
            value = func()
            self.set(key, value, timeout)
        return value
    
    def clear_pattern(self, pattern: str):
        """Clear cache keys matching pattern"""
        # Note: This requires Redis for pattern matching
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(f"*{pattern}*")

class DataFormatter:
    """Format weather data for display"""
    
    @staticmethod
    def format_temperature(temp: float, unit: str = 'celsius') -> str:
        """Format temperature with unit"""
        if unit == 'fahrenheit':
            temp = WeatherUtils.celsius_to_fahrenheit(temp)
            return f"{round(temp)}°F"
        return f"{round(temp)}°C"
    
    @staticmethod
    def format_wind_speed(speed: float, unit: str = 'metric') -> str:
        """Format wind speed with unit"""
        if unit == 'imperial':
            speed = WeatherUtils.ms_to_mph(speed)
            return f"{round(speed, 1)} mph"
        return f"{round(speed, 1)} m/s"
    
    @staticmethod
    def format_pressure(pressure: float) -> str:
        """Format pressure"""
        return f"{round(pressure)} hPa"
    
    @staticmethod
    def format_visibility(visibility: float) -> str:
        """Format visibility"""
        if visibility > 1000:
            return f"{round(visibility/1000, 1)} km"
        return f"{round(visibility)} m"
    
    @staticmethod
    def format_precipitation(precipitation: float) -> str:
        """Format precipitation"""
        return f"{precipitation} mm"
    
    @staticmethod
    def format_humidity(humidity: int) -> str:
        """Format humidity"""
        return f"{humidity}%"
    
    @staticmethod
    def format_date(date_str: str, format: str = '%Y-%m-%d') -> str:
        """Format date string"""
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            return date.strftime(format)
        except:
            return date_str
    
    @staticmethod
    def get_time_ago(timestamp: datetime) -> str:
        """Get human readable time ago"""
        now = timezone.now()
        diff = now - timestamp
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 7:
            weeks = diff.days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"