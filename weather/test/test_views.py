from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch, MagicMock
import json
from weather.models import SearchHistory, FavoriteCity, UserSettings

class HomeViewTest(TestCase):
    """Test home page view"""
    
    def setUp(self):
        self.client = Client()
        
    def test_home_view_status_code(self):
        """Test home page loads correctly"""
        response = self.client.get(reverse('weather:home'))
        self.assertEqual(response.status_code, 200)
        
    def test_home_view_template(self):
        """Test home page uses correct template"""
        response = self.client.get(reverse('weather:home'))
        self.assertTemplateUsed(response, 'weather/index.html')
        
    def test_home_view_context(self):
        """Test home page context data"""
        response = self.client.get(reverse('weather:home'))
        self.assertIn('featured_cities', response.context)
        self.assertEqual(len(response.context['featured_cities']), 6)

class DashboardViewTest(TestCase):
    """Test dashboard view"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_dashboard_requires_login(self):
        """Test dashboard redirects anonymous users"""
        response = self.client.get(reverse('weather:dashboard'))
        self.assertRedirects(response, '/accounts/login/?next=/dashboard/')
        
    def test_dashboard_authenticated(self):
        """Test authenticated users can access dashboard"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('weather:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'weather/dashboard.html')
        
    def test_dashboard_context(self):
        """Test dashboard context data"""
        self.client.login(username='testuser', password='testpass123')
        
        # Add some favorites
        FavoriteCity.objects.create(
            user=self.user,
            city_name='London',
            country='GB'
        )
        
        # Add search history
        SearchHistory.objects.create(
            user=self.user,
            city_name='Paris',
            country='FR'
        )
        
        response = self.client.get(reverse('weather:dashboard'))
        self.assertEqual(response.context['favorites'].count(), 1)
        self.assertEqual(response.context['recent_searches'].count(), 1)
        self.assertIsNotNone(response.context['settings'])

class WeatherAPITest(TestCase):
    """Test weather API endpoints"""
    
    def setUp(self):
        self.client = Client()
        
    @patch('weather.views.weather_service.fetch_weather_multiple_sources')
    def test_get_current_weather(self, mock_fetch):
        """Test current weather API"""
        mock_fetch.return_value = {
            'success': True,
            'data': {
                'city': 'London',
                'country': 'GB',
                'temperature': 15.5,
                'description': 'Cloudy'
            }
        }
        
        response = self.client.get(
            reverse('weather:api_current_weather'),
            {'city': 'London'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['city'], 'London')
        
    def test_get_current_weather_no_city(self):
        """Test current weather API with no city"""
        response = self.client.get(reverse('weather:api_current_weather'))
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        
    @patch('weather.views.weather_service.get_forecast')
    def test_get_forecast(self, mock_forecast):
        """Test forecast API"""
        mock_forecast.return_value = {
            'success': True,
            'data': {
                'city': 'London',
                'forecast': []
            }
        }
        
        response = self.client.get(
            reverse('weather:api_forecast'),
            {'city': 'London', 'days': 3}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
    def test_search_cities(self):
        """Test city search API"""
        response = self.client.get(
            reverse('weather:api_search'),
            {'q': 'Lon'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])