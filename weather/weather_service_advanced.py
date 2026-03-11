"""
Advanced Weather Service with multiple API sources and intelligent caching
"""
import asyncio
import aiohttp
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from typing import Dict, List, Optional, Any, Tuple
import logging
import json
import hashlib
import random
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import pandas as pd
import numpy as np
from collections import Counter
import time
import os
from .utils import WeatherUtils, CacheManager

logger = logging.getLogger(__name__)

class AdvancedWeatherService:
    """
    Advanced weather service with multiple API sources, 
    fallback mechanisms, and intelligent caching.
    """
    
    def __init__(self):
        # Get API configuration from settings or environment
        self.apis = self._get_api_config()
        self.geolocator = Nominatim(user_agent="weather_system_v2")
        self.session = None
        self.cache_manager = CacheManager()
        self.utils = WeatherUtils()
        self._mock_mode = False
        
        # Check if we have any valid API keys
        if not self._has_valid_api_keys():
            logger.warning("No valid API keys found. Running in mock mode.")
            self._mock_mode = True
    
    def _get_api_config(self) -> Dict:
        """Get API configuration from settings or environment variables"""
        # Try to get from settings first
        api_config = getattr(settings, 'WEATHER_API', {})
        
        # If not in settings, build from environment variables
        if not api_config:
            api_config = {
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
        
        return api_config
    
    def _has_valid_api_keys(self) -> bool:
        """Check if we have any valid API keys"""
        for api_name, config in self.apis.items():
            api_key = config.get('api_key', '')
            if api_key and api_key not in ['', 'your-actual-openweather-api-key-here']:
                return True
        return False
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(force_close=True)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    async def fetch_weather_multiple_sources(self, city: str) -> Dict[str, Any]:
        """
        Fetch weather data from multiple sources and aggregate results
        """
        # If in mock mode, return mock data
        if self._mock_mode:
            logger.info(f"Running in mock mode for {city}")
            return self._get_mock_weather_data(city)
        
        cache_key = self.utils.generate_cache_key("multi_weather", city=city)
        cached = self.cache_manager.get(cache_key)
        
        if cached:
            logger.info(f"Returning cached weather data for {city}")
            return cached
        
        results = {}
        errors = []
        
        # Try all APIs concurrently
        tasks = []
        api_names = []
        
        for api_name, api_config in self.apis.items():
            api_key = api_config.get('api_key', '')
            if api_name == 'primary' and api_key and api_key not in ['', 'your-actual-openweather-api-key-here']:
                tasks.append(self._fetch_openweather(city, api_config))
                api_names.append(api_name)
            elif api_name == 'secondary' and api_key and api_key not in ['', 'your-actual-openweather-api-key-here']:
                tasks.append(self._fetch_weatherapi(city, api_config))
                api_names.append(api_name)
            elif api_name == 'fallback':
                tasks.append(self._fetch_openmeteo(city, api_config))
                api_names.append(api_name)
        
        if not tasks:
            # No APIs configured, use mock data
            logger.warning("No weather APIs configured, using mock data")
            return self._get_mock_weather_data(city)
        
        # Gather results
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for api_name, result in zip(api_names, task_results):
            if isinstance(result, Exception):
                errors.append(f"{api_name}: {str(result)}")
                logger.error(f"Error fetching from {api_name}: {result}")
            else:
                results[api_name] = result
        
        # If primary API failed but others succeeded, use fallback
        if 'primary' not in results and results:
            logger.warning(f"Primary API failed, using fallback for {city}")
            # Use the first successful result
            results['primary'] = list(results.values())[0]
        
        if not results:
            # All APIs failed, use mock data
            logger.error(f"All APIs failed for {city}. Errors: {errors}")
            return self._get_mock_weather_data(city)
        
        # Aggregate and enhance data
        aggregated = self._aggregate_weather_data(results)
        aggregated['sources_used'] = list(results.keys())
        aggregated['errors'] = errors if errors else None
        aggregated['city'] = city
        aggregated['timestamp'] = datetime.now().isoformat()
        
        # Cache for 10 minutes
        self.cache_manager.set(cache_key, aggregated, 600)
        
        return aggregated
    
    async def _fetch_openweather(self, city: str, config: Dict) -> Dict:
        """Fetch from OpenWeatherMap API"""
        url = f"{config['url']}/weather"
        params = {
            'q': city,
            'appid': config['api_key'],
            'units': 'metric',
            'lang': 'en'
        }
        
        session = await self.get_session()
        
        for attempt in range(config.get('retries', 1)):
            try:
                async with session.get(url, params=params, timeout=config.get('timeout', 10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_openweather(data)
                    elif response.status == 404:
                        raise ValueError(f"City '{city}' not found")
                    else:
                        error_text = await response.text()
                        raise Exception(f"API error {response.status}: {error_text}")
            except asyncio.TimeoutError:
                if attempt == config.get('retries', 1) - 1:
                    raise
                await asyncio.sleep(1)
            except aiohttp.ClientError as e:
                logger.error(f"Client error in _fetch_openweather: {e}")
                if attempt == config.get('retries', 1) - 1:
                    raise
                await asyncio.sleep(1)
    
    async def _fetch_weatherapi(self, city: str, config: Dict) -> Dict:
        """Fetch from WeatherAPI.com"""
        url = f"{config['url']}/current.json"
        params = {
            'q': city,
            'key': config['api_key'],
            'aqi': 'yes'
        }
        
        session = await self.get_session()
        
        try:
            async with session.get(url, params=params, timeout=config.get('timeout', 10)) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_weatherapi(data)
                else:
                    error_text = await response.text()
                    raise Exception(f"WeatherAPI error: {error_text}")
        except Exception as e:
            logger.error(f"WeatherAPI fetch error: {e}")
            raise
    
    async def _fetch_openmeteo(self, city: str, config: Dict) -> Dict:
        """Fetch from Open-Meteo (free, no API key required)"""
        # First geocode the city
        try:
            location = await self._geocode_city(city)
            if not location:
                raise ValueError(f"Could not geocode city: {city}")
            
            lat, lon = location
            url = f"{config['url']}/forecast"
            params = {
                'latitude': lat,
                'longitude': lon,
                'current_weather': 'true',
                'hourly': 'temperature_2m,relativehumidity_2m,windspeed_10m,pressure_msl,weathercode',
                'daily': 'weathercode,temperature_2m_max,temperature_2m_min,sunrise,sunset',
                'timezone': 'auto'
            }
            
            session = await self.get_session()
            async with session.get(url, params=params, timeout=config.get('timeout', 15)) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_openmeteo(data, city, (lat, lon))
                else:
                    raise Exception(f"Open-Meteo error: {await response.text()}")
                    
        except Exception as e:
            logger.error(f"Open-Meteo fetch error: {e}")
            raise
    
    async def _geocode_city(self, city: str) -> Optional[Tuple[float, float]]:
        """Geocode city name to coordinates"""
        cache_key = self.utils.generate_cache_key("geocode", city=city)
        cached = self.cache_manager.get(cache_key)
        
        if cached:
            return cached
        
        try:
            # Run geocoding in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(
                None, 
                lambda: self.geolocator.geocode(city, timeout=10)
            )
            
            if location:
                coords = (location.latitude, location.longitude)
                self.cache_manager.set(cache_key, coords, 86400)  # Cache for 24 hours
                return coords
        except GeocoderTimedOut:
            logger.error(f"Geocoding timeout for {city}")
        except Exception as e:
            logger.error(f"Geocoding error for {city}: {e}")
        
        return None
    
    async def _reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """Reverse geocode coordinates to city name"""
        cache_key = self.utils.generate_cache_key("reverse_geocode", lat=lat, lon=lon)
        cached = self.cache_manager.get(cache_key)
        
        if cached:
            return cached
        
        try:
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(
                None,
                lambda: self.geolocator.reverse((lat, lon), timeout=10)
            )
            
            if location and location.raw.get('address'):
                address = location.raw['address']
                city = (address.get('city') or 
                       address.get('town') or 
                       address.get('village') or 
                       address.get('hamlet'))
                if city:
                    self.cache_manager.set(cache_key, city, 86400)
                    return city
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
        
        return None
    
    async def _search_cities(self, query: str) -> List[Dict]:
        """Search for cities by name"""
        cache_key = self.utils.generate_cache_key("search_cities", query=query)
        cached = self.cache_manager.get(cache_key)
        
        if cached:
            return cached
        
        try:
            loop = asyncio.get_event_loop()
            locations = await loop.run_in_executor(
                None,
                lambda: self.geolocator.geocode(query, exactly_one=False, limit=5, timeout=10)
            )
            
            results = []
            if locations:
                for location in locations:
                    results.append({
                        'name': location.address.split(',')[0],
                        'full_name': location.address,
                        'lat': location.latitude,
                        'lon': location.longitude,
                        'country': location.raw.get('address', {}).get('country', '')
                    })
            
            self.cache_manager.set(cache_key, results, 86400)
            return results
        except Exception as e:
            logger.error(f"City search error: {e}")
            return []
    
    def _parse_openweather(self, data: Dict) -> Dict:
        """Parse OpenWeatherMap response"""
        return {
            'source': 'openweather',
            'temperature': data['main']['temp'],
            'feels_like': data['main']['feels_like'],
            'humidity': data['main']['humidity'],
            'pressure': data['main']['pressure'],
            'description': data['weather'][0]['description'],
            'icon': data['weather'][0]['icon'],
            'wind_speed': data['wind']['speed'],
            'wind_direction': data['wind'].get('deg'),
            'wind_gust': data['wind'].get('gust'),
            'clouds': data['clouds']['all'],
            'visibility': data.get('visibility'),
            'sunrise': data['sys']['sunrise'],
            'sunset': data['sys']['sunset'],
            'coordinates': data['coord'],
            'country': data['sys']['country'],
            'city': data['name']
        }
    
    def _parse_weatherapi(self, data: Dict) -> Dict:
        """Parse WeatherAPI response"""
        current = data['current']
        location = data['location']
        return {
            'source': 'weatherapi',
            'temperature': current['temp_c'],
            'feels_like': current['feelslike_c'],
            'humidity': current['humidity'],
            'pressure': current['pressure_mb'],
            'description': current['condition']['text'],
            'icon': current['condition']['icon'].split('/')[-1].split('.')[0],
            'wind_speed': current['wind_kph'] / 3.6,  # Convert to m/s
            'wind_direction': current['wind_degree'],
            'wind_gust': current.get('gust_kph', 0) / 3.6,
            'clouds': current['cloud'],
            'visibility': current['vis_km'] * 1000,
            'uv_index': current['uv'],
            'air_quality': current.get('air_quality'),
            'country': location['country'],
            'city': location['name'],
            'coordinates': {
                'lat': location['lat'],
                'lon': location['lon']
            }
        }
    
    def _parse_openmeteo(self, data: Dict, city: str, coords: Tuple[float, float]) -> Dict:
        """Parse Open-Meteo response"""
        current = data['current_weather']
        hourly = data['hourly']
        
        # Get current hour's data
        current_time = datetime.now().strftime('%Y-%m-%dT%H:00')
        try:
            if current_time in hourly['time']:
                time_index = hourly['time'].index(current_time)
                humidity = hourly['relativehumidity_2m'][time_index]
                pressure = hourly['pressure_msl'][time_index]
                weathercode = hourly['weathercode'][time_index]
            else:
                # Use the first available hour
                humidity = hourly['relativehumidity_2m'][0]
                pressure = hourly['pressure_msl'][0]
                weathercode = hourly['weathercode'][0]
        except (ValueError, IndexError, KeyError):
            humidity = 50
            pressure = 1013
            weathercode = current.get('weathercode', 0)
        
        description, icon = self._get_weather_info(weathercode)
        
        # Get daily data
        daily = data.get('daily', {})
        sunrise = daily.get('sunrise', [None])[0] if daily.get('sunrise') else None
        sunset = daily.get('sunset', [None])[0] if daily.get('sunset') else None
        
        return {
            'source': 'openmeteo',
            'temperature': current['temperature'],
            'feels_like': current['temperature'],
            'humidity': humidity,
            'pressure': pressure,
            'description': description,
            'icon': icon,
            'wind_speed': current['windspeed'],
            'wind_direction': current.get('winddirection', 0),
            'clouds': 50,  # Open-Meteo doesn't provide clouds in current_weather
            'visibility': None,
            'sunrise': sunrise,
            'sunset': sunset,
            'coordinates': {
                'lat': coords[0],
                'lon': coords[1]
            },
            'city': city
        }
    
    def _get_weather_info(self, code: int) -> Tuple[str, str]:
        """Convert WMO weather code to description and icon"""
        weather_codes = {
            0: ('Clear sky', '01d'),
            1: ('Mainly clear', '02d'),
            2: ('Partly cloudy', '03d'),
            3: ('Overcast', '04d'),
            45: ('Fog', '50d'),
            48: ('Rime fog', '50d'),
            51: ('Light drizzle', '09d'),
            53: ('Moderate drizzle', '09d'),
            55: ('Dense drizzle', '09d'),
            56: ('Freezing drizzle', '09d'),
            57: ('Freezing drizzle', '09d'),
            61: ('Slight rain', '10d'),
            63: ('Moderate rain', '10d'),
            65: ('Heavy rain', '10d'),
            66: ('Freezing rain', '10d'),
            67: ('Freezing rain', '10d'),
            71: ('Slight snow', '13d'),
            73: ('Moderate snow', '13d'),
            75: ('Heavy snow', '13d'),
            77: ('Snow grains', '13d'),
            80: ('Slight rain showers', '09d'),
            81: ('Moderate rain showers', '09d'),
            82: ('Violent rain showers', '09d'),
            85: ('Slight snow showers', '13d'),
            86: ('Heavy snow showers', '13d'),
            95: ('Thunderstorm', '11d'),
            96: ('Thunderstorm with hail', '11d'),
            99: ('Thunderstorm with heavy hail', '11d')
        }
        return weather_codes.get(code, ('Unknown', '03d'))
    
    def _aggregate_weather_data(self, results: Dict) -> Dict:
        """
        Aggregate data from multiple sources with confidence scoring
        """
        if not results:
            return {}
        
        # Use primary if available, otherwise first available
        primary = results.get('primary', next(iter(results.values())) if results else None)
        
        if not primary:
            return {}
        
        # Collect all values for averaging
        temp_values = [r['temperature'] for r in results.values()]
        humidity_values = [r['humidity'] for r in results.values()]
        pressure_values = [r['pressure'] for r in results.values()]
        wind_speed_values = [r['wind_speed'] for r in results.values()]
        
        aggregated = {
            'city': primary.get('city', 'Unknown'),
            'country': primary.get('country', ''),
            'temperature': round(sum(temp_values) / len(temp_values), 1),
            'feels_like': primary.get('feels_like', primary['temperature']),
            'humidity': round(sum(humidity_values) / len(humidity_values)),
            'pressure': round(sum(pressure_values) / len(pressure_values)),
            'description': primary['description'],
            'icon': primary['icon'],
            'wind_speed': round(sum(wind_speed_values) / len(wind_speed_values), 1),
            'wind_direction': primary.get('wind_direction'),
            'wind_gust': primary.get('wind_gust'),
            'clouds': primary.get('clouds', 0),
            'visibility': primary.get('visibility'),
            'sunrise': primary.get('sunrise'),
            'sunset': primary.get('sunset'),
            'coordinates': primary.get('coordinates', {}),
            'uv_index': primary.get('uv_index'),
        }
        
        # Add advanced metrics if available from any source
        advanced_metrics = {}
        for source, data in results.items():
            if 'uv_index' in data and data['uv_index']:
                advanced_metrics['uv_index'] = data['uv_index']
            if 'air_quality' in data and data['air_quality']:
                advanced_metrics['air_quality'] = data['air_quality']
        
        if advanced_metrics:
            aggregated['advanced'] = advanced_metrics
        
        # Add thermal sensation
        aggregated['thermal_sensation'] = self.utils.get_thermal_sensation(
            aggregated['temperature'],
            aggregated['wind_speed'],
            aggregated['humidity']
        )
        
        # Calculate confidence score
        aggregated['confidence'] = self._calculate_confidence(results)
        
        return aggregated
    
    def _calculate_confidence(self, results: Dict) -> float:
        """Calculate confidence score based on available data"""
        weights = {
            'primary': 1.0,
            'secondary': 0.8,
            'fallback': 0.6
        }
        
        if not results:
            return 0.0
        
        total_weight = 0
        weighted_score = 0
        
        for source, data in results.items():
            weight = weights.get(source, 0.5)
            total_weight += weight
            
            # Check data completeness
            required_fields = ['temperature', 'humidity', 'pressure', 'wind_speed']
            completeness = sum(1 for f in required_fields if f in data and data[f] is not None) / len(required_fields)
            weighted_score += weight * completeness
        
        return round(weighted_score / total_weight, 2) if total_weight > 0 else 0.5
    
    def _get_mock_weather_data(self, city: str) -> Dict:
        """Generate mock weather data for development"""
        conditions = [
            ('Sunny', '01d'),
            ('Partly cloudy', '02d'),
            ('Cloudy', '03d'),
            ('Overcast', '04d'),
            ('Light rain', '10d'),
            ('Moderate rain', '10d'),
            ('Heavy rain', '10d'),
            ('Thunderstorm', '11d'),
            ('Snow', '13d'),
            ('Fog', '50d')
        ]
        description, icon = random.choice(conditions)
        
        return {
            'city': city,
            'country': 'US',
            'temperature': round(random.uniform(5, 35), 1),
            'feels_like': round(random.uniform(5, 35), 1),
            'humidity': random.randint(30, 95),
            'pressure': random.randint(980, 1040),
            'description': description,
            'icon': icon,
            'wind_speed': round(random.uniform(0, 15), 1),
            'wind_direction': random.randint(0, 360),
            'clouds': random.randint(0, 100),
            'visibility': random.randint(1000, 10000),
            'sunrise': int(datetime.now().replace(hour=6, minute=0).timestamp()),
            'sunset': int(datetime.now().replace(hour=18, minute=0).timestamp()),
            'coordinates': {'lat': 40.7128, 'lon': -74.0060},
            'uv_index': round(random.uniform(0, 10), 1),
            'sources_used': ['mock'],
            'confidence': 0.5,
            'timestamp': datetime.now().isoformat()
        }
    
    async def get_forecast(self, city: str, days: int = 5) -> Dict:
        """Get weather forecast for a city"""
        if self._mock_mode:
            return self._get_mock_forecast(city, days)
        
        cache_key = self.utils.generate_cache_key("forecast", city=city, days=days)
        cached = self.cache_manager.get(cache_key)
        
        if cached:
            return cached
        
        try:
            # Use OpenWeatherMap forecast API
            config = self.apis.get('primary', {})
            if not config or not config.get('api_key'):
                return self._get_mock_forecast(city, days)
            
            url = f"{config['url']}/forecast"
            params = {
                'q': city,
                'appid': config['api_key'],
                'units': 'metric',
                'cnt': days * 8  # 8 forecasts per day (3-hour intervals)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        forecast = self._parse_forecast(data, days)
                        self.cache_manager.set(cache_key, forecast, 1800)  # 30 minutes
                        return forecast
                    else:
                        raise Exception(f"Forecast API error: {response.status}")
        except Exception as e:
            logger.error(f"Forecast fetch error: {e}")
            return self._get_mock_forecast(city, days)
    
    def _parse_forecast(self, data: Dict, days: int) -> Dict:
        """Parse forecast data"""
        forecasts = []
        daily_data = {}
        
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            date = dt.date()
            day_name = dt.strftime('%A')
            
            if date not in daily_data:
                daily_data[date] = {
                    'date': date.isoformat(),
                    'day_name': day_name,
                    'temp_min': item['main']['temp_min'],
                    'temp_max': item['main']['temp_max'],
                    'humidity': [],
                    'descriptions': [],
                    'icons': [],
                    'wind_speeds': [],
                    'pop': []  # Probability of precipitation
                }
            
            # Update min/max
            daily_data[date]['temp_min'] = min(daily_data[date]['temp_min'], item['main']['temp_min'])
            daily_data[date]['temp_max'] = max(daily_data[date]['temp_max'], item['main']['temp_max'])
            
            # Collect data for averages
            daily_data[date]['humidity'].append(item['main']['humidity'])
            daily_data[date]['descriptions'].append(item['weather'][0]['description'])
            daily_data[date]['icons'].append(item['weather'][0]['icon'])
            daily_data[date]['wind_speeds'].append(item['wind']['speed'])
            daily_data[date]['pop'].append(item.get('pop', 0) * 100)
        
        # Calculate averages and most common values
        for date, values in daily_data.items():
            most_common_desc = Counter(values['descriptions']).most_common(1)[0][0]
            most_common_icon = Counter(values['icons']).most_common(1)[0][0]
            
            forecasts.append({
                'date': values['date'],
                'day_name': values['day_name'],
                'temp_min': round(values['temp_min']),
                'temp_max': round(values['temp_max']),
                'humidity': round(sum(values['humidity']) / len(values['humidity'])),
                'description': most_common_desc,
                'icon': most_common_icon,
                'wind_speed': round(sum(values['wind_speeds']) / len(values['wind_speeds']), 1),
                'pop': round(sum(values['pop']) / len(values['pop']))
            })
        
        # Sort by date and limit to requested days
        forecasts.sort(key=lambda x: x['date'])
        
        return {
            'city': data['city']['name'],
            'country': data['city']['country'],
            'forecast': forecasts[:days]
        }
    
    def _get_mock_forecast(self, city: str, days: int) -> Dict:
        """Generate mock forecast data"""
        forecasts = []
        start_date = datetime.now()
        
        for i in range(days):
            date = start_date + timedelta(days=i)
            temp_min = random.randint(10, 18)
            temp_max = temp_min + random.randint(5, 12)
            forecasts.append({
                'date': date.date().isoformat(),
                'day_name': date.strftime('%A'),
                'temp_min': temp_min,
                'temp_max': temp_max,
                'humidity': random.randint(50, 85),
                'description': random.choice(['Sunny', 'Partly cloudy', 'Cloudy', 'Light rain']),
                'icon': random.choice(['01d', '02d', '03d', '10d']),
                'wind_speed': round(random.uniform(2, 8), 1),
                'pop': random.randint(0, 60)
            })
        
        return {
            'city': city,
            'country': 'US',
            'forecast': forecasts
        }
    
    async def get_air_quality(self, lat: float, lon: float) -> Dict:
        """Get air quality data"""
        if self._mock_mode:
            return self._get_mock_air_quality()
        
        cache_key = self.utils.generate_cache_key("air_quality", lat=lat, lon=lon)
        cached = self.cache_manager.get(cache_key)
        
        if cached:
            return cached
        
        try:
            config = self.apis.get('primary', {})
            if not config or not config.get('api_key'):
                return self._get_mock_air_quality()
            
            url = f"{config['url']}/air_pollution"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': config['api_key']
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        air_quality = self._parse_air_quality(data)
                        self.cache_manager.set(cache_key, air_quality, 3600)  # 1 hour
                        return air_quality
                    else:
                        raise Exception(f"Air quality API error: {response.status}")
        except Exception as e:
            logger.error(f"Air quality fetch error: {e}")
            return self._get_mock_air_quality()
    
    def _parse_air_quality(self, data: Dict) -> Dict:
        """Parse air quality data"""
        if not data or 'list' not in data or len(data['list']) == 0:
            return {'error': 'No air quality data available'}
        
        item = data['list'][0]
        components = item['components']
        aqi = item['main']['aqi']
        
        return {
            'aqi': aqi,
            'aqi_label': self.utils.get_air_quality_label(aqi),
            'aqi_color': self.utils.get_air_quality_color(aqi),
            'components': {
                'co': round(components.get('co', 0), 1),
                'no': round(components.get('no', 0), 1),
                'no2': round(components.get('no2', 0), 1),
                'o3': round(components.get('o3', 0), 1),
                'so2': round(components.get('so2', 0), 1),
                'pm2_5': round(components.get('pm2_5', 0), 1),
                'pm10': round(components.get('pm10', 0), 1),
                'nh3': round(components.get('nh3', 0), 1)
            }
        }
    
    def _get_mock_air_quality(self) -> Dict:
        """Generate mock air quality data"""
        aqi = random.randint(1, 5)
        return {
            'aqi': aqi,
            'aqi_label': self.utils.get_air_quality_label(aqi),
            'aqi_color': self.utils.get_air_quality_color(aqi),
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
    
    async def get_historical_data(self, city: str, days: int = 7) -> Dict:
        """Get historical weather data"""
        if self._mock_mode:
            return self._get_mock_historical_data(city, days)
        
        cache_key = self.utils.generate_cache_key("historical", city=city, days=days)
        cached = self.cache_manager.get(cache_key)
        
        if cached:
            return cached
        
        # Get coordinates
        coords = await self._geocode_city(city)
        if not coords:
            return {'error': 'Could not geocode city'}
        
        lat, lon = coords
        
        # Use Open-Meteo historical API
        url = "https://archive-api.open-meteo.com/v1/archive"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'daily': 'temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,windspeed_10m_max',
            'timezone': 'auto'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        historical = {
                            'city': city,
                            'days': days,
                            'data': []
                        }
                        
                        for i, date in enumerate(data['daily']['time']):
                            historical['data'].append({
                                'date': date,
                                'temp_max': data['daily']['temperature_2m_max'][i],
                                'temp_min': data['daily']['temperature_2m_min'][i],
                                'temp_mean': data['daily']['temperature_2m_mean'][i],
                                'precipitation': data['daily']['precipitation_sum'][i],
                                'wind_max': data['daily']['windspeed_10m_max'][i]
                            })
                        
                        self.cache_manager.set(cache_key, historical, 3600)  # 1 hour
                        return historical
        except Exception as e:
            logger.error(f"Historical data error: {e}")
        
        return self._get_mock_historical_data(city, days)
    
    def _get_mock_historical_data(self, city: str, days: int) -> Dict:
        """Generate mock historical data"""
        historical = {
            'city': city,
            'days': days,
            'data': []
        }
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            historical['data'].append({
                'date': date.strftime('%Y-%m-%d'),
                'temp_max': random.randint(22, 28),
                'temp_min': random.randint(15, 21),
                'temp_mean': random.randint(18, 24),
                'precipitation': round(random.uniform(0, 10), 1),
                'wind_max': random.randint(10, 25)
            })
        
        return historical
    
    async def get_weather_alerts(self, city: str) -> List[Dict]:
        """Get weather alerts for a city"""
        if self._mock_mode:
            return self._get_mock_alerts()
        
        cache_key = self.utils.generate_cache_key("alerts", city=city)
        cached = self.cache_manager.get(cache_key)
        
        if cached:
            return cached
        
        # Get coordinates
        coords = await self._geocode_city(city)
        if not coords:
            return []
        
        lat, lon = coords
        
        # Try multiple alert sources
        alerts = []
        
        # Source 1: OpenWeatherMap alerts (if available)
        try:
            config = self.apis.get('primary', {})
            if config.get('api_key'):
                url = f"{config['url']}/onecall"
                params = {
                    'lat': lat,
                    'lon': lon,
                    'appid': config['api_key'],
                    'exclude': 'current,minutely,hourly,daily'
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'alerts' in data:
                                for alert in data['alerts']:
                                    alerts.append({
                                        'source': 'OpenWeatherMap',
                                        'title': alert.get('event', 'Weather Alert'),
                                        'description': alert.get('description', ''),
                                        'severity': self._map_alert_severity(alert.get('severity', '')),
                                        'start_time': datetime.fromtimestamp(alert['start']).isoformat(),
                                        'end_time': datetime.fromtimestamp(alert['end']).isoformat(),
                                        'tags': alert.get('tags', [])
                                    })
        except Exception as e:
            logger.error(f"Error fetching alerts from OpenWeatherMap: {e}")
        
        # Source 2: Weather.gov alerts (US only)
        if -160 <= lon <= -60 and 20 <= lat <= 70:  # US coordinates approximate
            try:
                url = "https://api.weather.gov/alerts/active"
                params = {
                    'point': f"{lat},{lon}"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            for feature in data.get('features', []):
                                props = feature['properties']
                                alerts.append({
                                    'source': 'weather.gov',
                                    'title': props.get('headline', 'Weather Alert'),
                                    'description': props.get('description', ''),
                                    'instruction': props.get('instruction', ''),
                                    'severity': props.get('severity', '').lower(),
                                    'start_time': props.get('effective'),
                                    'end_time': props.get('expires'),
                                    'areas': props.get('areaDesc')
                                })
            except Exception as e:
                logger.error(f"Error fetching alerts from weather.gov: {e}")
        
        # If no alerts found, return mock alerts 10% of the time
        if not alerts and random.random() < 0.1:
            alerts = self._get_mock_alerts()
        
        # Cache alerts for 15 minutes
        self.cache_manager.set(cache_key, alerts, 900)
        
        return alerts
    
    def _get_mock_alerts(self) -> List[Dict]:
        """Generate mock weather alerts"""
        alert_types = [
            ('Heavy Rain Warning', 'Heavy rainfall expected in the area', 'moderate'),
            ('Thunderstorm Watch', 'Conditions favorable for thunderstorms', 'moderate'),
            ('Flood Advisory', 'Minor flooding in low-lying areas', 'minor'),
            ('Heat Wave', 'Extreme heat conditions', 'severe'),
            ('Wind Advisory', 'Strong winds expected', 'minor'),
        ]
        
        title, desc, severity = random.choice(alert_types)
        
        return [{
            'source': 'Weather Service',
            'title': title,
            'description': desc,
            'instruction': 'Stay informed and follow local authorities\' guidance.',
            'severity': severity,
            'start_time': datetime.now().isoformat(),
            'end_time': (datetime.now() + timedelta(days=1)).isoformat(),
            'areas': 'Local Area'
        }]
    
    def _map_alert_severity(self, severity: str) -> str:
        """Map API severity to standard severity levels"""
        severity_map = {
            'extreme': 'extreme',
            'severe': 'severe',
            'moderate': 'moderate',
            'minor': 'minor',
            'warning': 'severe',
            'watch': 'moderate',
            'advisory': 'minor',
            'statement': 'minor'
        }
        return severity_map.get(severity.lower(), 'moderate')