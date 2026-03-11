from django.test import TestCase
from unittest.mock import patch, MagicMock, AsyncMock
from weather.weather_service_advanced import AdvancedWeatherService
import asyncio

class WeatherServiceTest(TestCase):
    """Test advanced weather service"""
    
    def setUp(self):
        self.service = AdvancedWeatherService()
        
    @patch('weather.weather_service_advanced.AdvancedWeatherService._fetch_openweather')
    async def test_fetch_weather_multiple_sources(self, mock_fetch):
        """Test fetching from multiple sources"""
        mock_fetch.return_value = {
            'source': 'openweather',
            'temperature': 20,
            'humidity': 65
        }
        
        result = await self.service.fetch_weather_multiple_sources('London')
        self.assertIn('city', result)
        self.assertIn('sources_used', result)
        self.assertEqual(result['city'], 'London')
        
    def test_calculate_confidence(self):
        """Test confidence score calculation"""
        results = {
            'primary': {'temperature': 20, 'humidity': 65, 'pressure': 1013, 'wind_speed': 5},
            'secondary': {'temperature': 19, 'humidity': 70, 'pressure': 1012, 'wind_speed': 4.5}
        }
        confidence = self.service._calculate_confidence(results)
        self.assertGreater(confidence, 0)
        self.assertLessEqual(confidence, 1.0)
        
    def test_get_weather_info(self):
        """Test weather code conversion"""
        description, icon = self.service._get_weather_info(0)
        self.assertEqual(description, 'Clear sky')
        self.assertEqual(icon, '01d')
        
        description, icon = self.service._get_weather_info(95)
        self.assertEqual(description, 'Thunderstorm')
        self.assertEqual(icon, '11d')
        
    def test_mock_weather_data(self):
        """Test mock data generation"""
        mock_data = self.service._get_mock_weather_data('Test City')
        self.assertEqual(mock_data['city'], 'Test City')
        self.assertIn('temperature', mock_data)
        self.assertIn('humidity', mock_data)
        self.assertIn('description', mock_data)