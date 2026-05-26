"""
Additional weather API providers
"""
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class WeatherProvider:
    """Base class for weather providers"""
    
    def __init__(self, api_key: str = None, timeout: int = 10):
        self.api_key = api_key
        self.timeout = timeout
        
    async def fetch(self, url: str, params: Dict) -> Optional[Dict]:
        """Make async HTTP request"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=self.timeout) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API error {response.status}: {await response.text()}")
                        return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

class AccuWeatherProvider(WeatherProvider):
    """AccuWeather API provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "http://dataservice.accuweather.com"
        
    async def get_location_key(self, city: str) -> Optional[str]:
        """Get location key for city"""
        url = f"{self.base_url}/locations/v1/cities/search"
        params = {
            'apikey': self.api_key,
            'q': city,
            'language': 'en-us'
        }
        
        data = await self.fetch(url, params)
        if data and len(data) > 0:
            return data[0]['Key']
        return None
        
    async def get_current_weather(self, city: str) -> Optional[Dict]:
        """Get current weather from AccuWeather"""
        location_key = await self.get_location_key(city)
        if not location_key:
            return None
            
        url = f"{self.base_url}/currentconditions/v1/{location_key}"
        params = {
            'apikey': self.api_key,
            'details': 'true',
            'language': 'en-us'
        }
        
        data = await self.fetch(url, params)
        if data and len(data) > 0:
            return self.parse_current(data[0])
        return None
        
    def parse_current(self, data: Dict) -> Dict:
        """Parse AccuWeather response"""
        return {
            'source': 'accuweather',
            'temperature': data['Temperature']['Metric']['Value'],
            'feels_like': data.get('RealFeelTemperature', {}).get('Metric', {}).get('Value'),
            'humidity': data.get('RelativeHumidity'),
            'wind_speed': data.get('Wind', {}).get('Speed', {}).get('Metric', {}).get('Value'),
            'wind_direction': data.get('Wind', {}).get('Direction', {}).get('Degrees'),
            'pressure': data.get('Pressure', {}).get('Metric', {}).get('Value'),
            'visibility': data.get('Visibility', {}).get('Metric', {}).get('Value'),
            'uv_index': data.get('UVIndex'),
            'cloud_cover': data.get('CloudCover'),
            'description': data.get('WeatherText'),
            'icon': self.get_icon_code(data.get('WeatherIcon'))
        }
        
    def get_icon_code(self, icon: int) -> str:
        """Convert AccuWeather icon to OpenWeatherMap style"""
        icon_map = {
            1: '01d', 2: '02d', 3: '03d', 4: '04d', 5: '04d',
            6: '09d', 7: '10d', 8: '10d', 9: '10d', 10: '10d',
            11: '10d', 12: '10d', 13: '10d', 14: '13d', 15: '13d',
            16: '13d', 17: '13d', 18: '11d', 19: '50d', 20: '50d',
            21: '50d', 22: '50d', 23: '50d', 24: '50d', 25: '13d',
            26: '09d', 27: '02d', 28: '02d', 29: '02d', 30: '02d',
            31: '02d', 32: '01d', 33: '01d', 34: '01d', 35: '01d',
            36: '01d', 37: '11d', 38: '11d', 39: '10d', 40: '10d',
            41: '13d', 42: '13d', 43: '13d', 44: '13d'
        }
        return icon_map.get(icon, '03d')

class WeatherBitProvider(WeatherProvider):
    """WeatherBit API provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.weatherbit.io/v2.0"
        
    async def get_current_weather(self, city: str) -> Optional[Dict]:
        """Get current weather from WeatherBit"""
        url = f"{self.base_url}/current"
        params = {
            'key': self.api_key,
            'city': city,
            'units': 'M',
            'lang': 'en'
        }
        
        data = await self.fetch(url, params)
        if data and 'data' in data and len(data['data']) > 0:
            return self.parse_current(data['data'][0])
        return None
        
    def parse_current(self, data: Dict) -> Dict:
        """Parse WeatherBit response"""
        return {
            'source': 'weatherbit',
            'temperature': data.get('temp'),
            'feels_like': data.get('app_temp'),
            'humidity': data.get('rh'),
            'wind_speed': data.get('wind_spd'),
            'wind_direction': data.get('wind_dir'),
            'wind_gust': data.get('gust'),
            'pressure': data.get('pres'),
            'visibility': data.get('vis'),
            'uv_index': data.get('uv'),
            'clouds': data.get('clouds'),
            'description': data.get('weather', {}).get('description'),
            'icon': data.get('weather', {}).get('icon')
        }

class Weather2020Provider(WeatherProvider):
    """Weather2020 API provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.weather2020.com"
        
    async def get_current_weather(self, city: str, country: str = 'US') -> Optional[Dict]:
        """Get current weather from Weather2020"""
        url = f"{self.base_url}/v1/current"
        params = {
            'key': self.api_key,
            'city': city,
            'country': country,
            'units': 'm'
        }
        
        data = await self.fetch(url, params)
        if data:
            return self.parse_current(data)
        return None
        
    def parse_current(self, data: Dict) -> Dict:
        """Parse Weather2020 response"""
        return {
            'source': 'weather2020',
            'temperature': data.get('temp_c'),
            'feels_like': data.get('feels_like_c'),
            'humidity': data.get('humidity'),
            'wind_speed': data.get('wind_kph') / 3.6,
            'wind_direction': data.get('wind_degrees'),
            'pressure': data.get('pressure_mb'),
            'visibility': data.get('visibility_km') * 1000,
            'uv_index': data.get('uv_index'),
            'cloud_cover': data.get('cloud_cover_percent'),
            'description': data.get('condition_text'),
            'icon': data.get('condition_icon')
        }

class WeatherAPIComProvider(WeatherProvider):
    """WeatherAPI.com provider (comprehensive alternative)"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "http://api.weatherapi.com/v1"
        
    async def get_current_weather(self, city: str) -> Optional[Dict]:
        """Get current weather from WeatherAPI.com"""
        url = f"{self.base_url}/current.json"
        params = {
            'key': self.api_key,
            'q': city,
            'aqi': 'yes',
            'alerts': 'yes'
        }
        
        data = await self.fetch(url, params)
        if data:
            return self.parse_current(data)
        return None
        
    async def get_forecast(self, city: str, days: int = 5) -> Optional[Dict]:
        """Get forecast from WeatherAPI.com"""
        url = f"{self.base_url}/forecast.json"
        params = {
            'key': self.api_key,
            'q': city,
            'days': days,
            'aqi': 'yes',
            'alerts': 'yes'
        }
        
        data = await self.fetch(url, params)
        if data:
            return self.parse_forecast(data)
        return None
        
    async def get_history(self, city: str, date: str) -> Optional[Dict]:
        """Get historical weather"""
        url = f"{self.base_url}/history.json"
        params = {
            'key': self.api_key,
            'q': city,
            'dt': date
        }
        
        data = await self.fetch(url, params)
        if data:
            return self.parse_history(data)
        return None
        
    def parse_current(self, data: Dict) -> Dict:
        """Parse WeatherAPI.com current response"""
        current = data['current']
        location = data['location']
        
        return {
            'source': 'weatherapi_com',
            'temperature': current['temp_c'],
            'feels_like': current['feelslike_c'],
            'humidity': current['humidity'],
            'wind_speed': current['wind_kph'] / 3.6,
            'wind_direction': current['wind_degree'],
            'wind_gust': current.get('gust_kph', 0) / 3.6,
            'pressure': current['pressure_mb'],
            'visibility': current['vis_km'] * 1000,
            'uv_index': current['uv'],
            'clouds': current['cloud'],
            'description': current['condition']['text'],
            'icon': self.get_icon_code(current['condition']['code']),
            'air_quality': current.get('air_quality'),
            'precipitation': current.get('precip_mm'),
            'is_day': current.get('is_day') == 1,
            'city': location['name'],
            'country': location['country'],
            'coordinates': {
                'lat': location['lat'],
                'lon': location['lon']
            }
        }
        
    def parse_forecast(self, data: Dict) -> Dict:
        """Parse WeatherAPI.com forecast response"""
        forecast_days = []
        
        for day in data['forecast']['forecastday']:
            forecast_days.append({
                'date': day['date'],
                'max_temp': day['day']['maxtemp_c'],
                'min_temp': day['day']['mintemp_c'],
                'avg_temp': day['day']['avgtemp_c'],
                'max_wind': day['day']['maxwind_kph'] / 3.6,
                'total_precip': day['day']['totalprecip_mm'],
                'avg_humidity': day['day']['avghumidity'],
                'condition': day['day']['condition']['text'],
                'icon': self.get_icon_code(day['day']['condition']['code']),
                'uv_index': day['day']['uv'],
                'sunrise': day['astro']['sunrise'],
                'sunset': day['astro']['sunset'],
                'moonrise': day['astro']['moonrise'],
                'moonset': day['astro']['moonset'],
                'moon_phase': day['astro']['moon_phase'],
                'hourly': [{
                    'time': hour['time'].split(' ')[1],
                    'temp': hour['temp_c'],
                    'feels_like': hour['feelslike_c'],
                    'humidity': hour['humidity'],
                    'wind_speed': hour['wind_kph'] / 3.6,
                    'wind_direction': hour['wind_degree'],
                    'pressure': hour['pressure_mb'],
                    'visibility': hour['vis_km'] * 1000,
                    'clouds': hour['cloud'],
                    'chance_of_rain': hour['chance_of_rain'],
                    'chance_of_snow': hour['chance_of_snow'],
                    'condition': hour['condition']['text'],
                    'icon': self.get_icon_code(hour['condition']['code'])
                } for hour in day['hour']]
            })
            
        return {
            'city': data['location']['name'],
            'country': data['location']['country'],
            'forecast': forecast_days
        }
        
    def parse_history(self, data: Dict) -> Dict:
        """Parse WeatherAPI.com historical response"""
        return self.parse_forecast(data)  # Similar structure
        
    def get_icon_code(self, code: int) -> str:
        """Convert WeatherAPI.com condition code to icon"""
        icon_map = {
            1000: '01d',  # Clear
            1003: '02d',  # Partly cloudy
            1006: '03d',  # Cloudy
            1009: '04d',  # Overcast
            1030: '50d',  # Mist
            1063: '09d',  # Patchy rain possible
            1066: '13d',  # Patchy snow possible
            1069: '09d',  # Patchy sleet possible
            1072: '09d',  # Patchy freezing drizzle possible
            1087: '11d',  # Thundery outbreaks possible
            1114: '13d',  # Blowing snow
            1117: '13d',  # Blizzard
            1135: '50d',  # Fog
            1147: '50d',  # Freezing fog
            1150: '09d',  # Patchy light drizzle
            1153: '09d',  # Light drizzle
            1168: '09d',  # Freezing drizzle
            1171: '09d',  # Heavy freezing drizzle
            1180: '10d',  # Patchy light rain
            1183: '10d',  # Light rain
            1186: '10d',  # Moderate rain at times
            1189: '10d',  # Moderate rain
            1192: '10d',  # Heavy rain at times
            1195: '10d',  # Heavy rain
            1198: '09d',  # Light freezing rain
            1201: '09d',  # Moderate or heavy freezing rain
            1204: '13d',  # Light sleet
            1207: '13d',  # Moderate or heavy sleet
            1210: '13d',  # Patchy light snow
            1213: '13d',  # Light snow
            1216: '13d',  # Patchy moderate snow
            1219: '13d',  # Moderate snow
            1222: '13d',  # Patchy heavy snow
            1225: '13d',  # Heavy snow
            1237: '13d',  # Ice pellets
            1240: '10d',  # Light rain shower
            1243: '10d',  # Moderate or heavy rain shower
            1246: '10d',  # Torrential rain shower
            1249: '13d',  # Light sleet showers
            1252: '13d',  # Moderate or heavy sleet showers
            1255: '13d',  # Light snow showers
            1258: '13d',  # Moderate or heavy snow showers
            1261: '13d',  # Light showers of ice pellets
            1264: '13d',  # Moderate or heavy showers of ice pellets
            1273: '11d',  # Patchy light rain with thunder
            1276: '11d',  # Moderate or heavy rain with thunder
            1279: '11d',  # Patchy light snow with thunder
            1282: '11d'   # Moderate or heavy snow with thunder
        }
        return icon_map.get(code, '03d')