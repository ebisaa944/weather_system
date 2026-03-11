from django.test import TestCase
from weather.utils import WeatherUtils, DataFormatter, CacheManager
from datetime import datetime

class WeatherUtilsTest(TestCase):
    """Test utility functions"""
    
    def setUp(self):
        self.utils = WeatherUtils()
        
    def test_temperature_conversion(self):
        """Test temperature conversion functions"""
        celsius = 25
        fahrenheit = self.utils.celsius_to_fahrenheit(celsius)
        self.assertEqual(fahrenheit, 77)
        
        back_to_celsius = self.utils.fahrenheit_to_celsius(fahrenheit)
        self.assertEqual(back_to_celsius, 25)
        
    def test_wind_conversion(self):
        """Test wind speed conversion"""
        ms = 10
        mph = self.utils.ms_to_mph(ms)
        self.assertAlmostEqual(mph, 22.3694, places=2)
        
        back_to_ms = self.utils.mph_to_ms(mph)
        self.assertAlmostEqual(back_to_ms, 10, places=1)
        
    def test_wind_direction(self):
        """Test wind direction conversion"""
        self.assertEqual(self.utils.get_wind_direction(0), 'N')
        self.assertEqual(self.utils.get_wind_direction(90), 'E')
        self.assertEqual(self.utils.get_wind_direction(180), 'S')
        self.assertEqual(self.utils.get_wind_direction(270), 'W')
        
    def test_air_quality_label(self):
        """Test AQI label mapping"""
        self.assertEqual(self.utils.get_air_quality_label(1), 'Good')
        self.assertEqual(self.utils.get_air_quality_label(3), 'Moderate')
        self.assertEqual(self.utils.get_air_quality_label(5), 'Very Poor')
        
    def test_air_quality_color(self):
        """Test AQI color mapping"""
        self.assertEqual(self.utils.get_air_quality_color(1), '#00e400')
        self.assertEqual(self.utils.get_air_quality_color(3), '#ff7e00')
        self.assertEqual(self.utils.get_air_quality_color(5), '#8f3f97')
        
    def test_validate_city_name(self):
        """Test city name validation"""
        self.assertTrue(self.utils.validate_city_name('London'))
        self.assertTrue(self.utils.validate_city_name('New York'))
        self.assertTrue(self.utils.validate_city_name('San Francisco'))
        self.assertFalse(self.utils.validate_city_name('L'))
        self.assertFalse(self.utils.validate_city_name('London123'))
        
    def test_format_time(self):
        """Test time formatting"""
        timestamp = datetime(2024, 1, 1, 14, 30).timestamp()
        self.assertEqual(self.utils.format_time(timestamp, '24h'), '14:30')
        self.assertEqual(self.utils.format_time(timestamp, '12h'), '02:30 PM')
        
    def test_dew_point_calculation(self):
        """Test dew point calculation"""
        dew_point = self.utils.calculate_dew_point(25, 60)
        self.assertIsNotNone(dew_point)
        
    def test_thermal_sensation(self):
        """Test thermal sensation calculation"""
        # Wind chill
        sensation = self.utils.get_thermal_sensation(5, 10, 70)
        self.assertEqual(sensation['type'], 'wind_chill')
        
        # Heat index
        sensation = self.utils.get_thermal_sensation(30, 2, 80)
        self.assertEqual(sensation['type'], 'heat_index')
        
        # Normal
        sensation = self.utils.get_thermal_sensation(20, 2, 50)
        self.assertEqual(sensation['type'], 'normal')
        
    def test_uv_index_risk(self):
        """Test UV index risk levels"""
        risk = self.utils.get_uv_index_risk(2)
        self.assertEqual(risk['level'], 'Low')
        
        risk = self.utils.get_uv_index_risk(5)
        self.assertEqual(risk['level'], 'Moderate')
        
        risk = self.utils.get_uv_index_risk(10)
        self.assertEqual(risk['level'], 'Very High')

class DataFormatterTest(TestCase):
    """Test data formatting functions"""
    
    def setUp(self):
        self.formatter = DataFormatter()
        
    def test_format_temperature(self):
        """Test temperature formatting"""
        self.assertEqual(self.formatter.format_temperature(25), '25°C')
        self.assertEqual(self.formatter.format_temperature(25, 'fahrenheit'), '77°F')
        
    def test_format_wind_speed(self):
        """Test wind speed formatting"""
        self.assertEqual(self.formatter.format_wind_speed(5), '5 m/s')
        self.assertEqual(self.formatter.format_wind_speed(5, 'imperial'), '11.2 mph')
        
    def test_format_pressure(self):
        """Test pressure formatting"""
        self.assertEqual(self.formatter.format_pressure(1013.25), '1013 hPa')
        
    def test_format_visibility(self):
        """Test visibility formatting"""
        self.assertEqual(self.formatter.format_visibility(10000), '10 km')
        self.assertEqual(self.formatter.format_visibility(500), '500 m')
        
    def test_format_humidity(self):
        """Test humidity formatting"""
        self.assertEqual(self.formatter.format_humidity(65), '65%')
        
    def test_get_time_ago(self):
        """Test time ago formatting"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        
        # Just now
        self.assertEqual(self.formatter.get_time_ago(now), 'Just now')
        
        # Minutes ago
        minutes_ago = now - timedelta(minutes=5)
        self.assertEqual(self.formatter.get_time_ago(minutes_ago), '5 minutes ago')
        
        # Hours ago
        hours_ago = now - timedelta(hours=3)
        self.assertEqual(self.formatter.get_time_ago(hours_ago), '3 hours ago')
        
        # Days ago
        days_ago = now - timedelta(days=2)
        self.assertEqual(self.formatter.get_time_ago(days_ago), '2 days ago')