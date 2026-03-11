from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from weather.models import (
    SearchHistory, FavoriteCity, WeatherAlert, 
    UserSettings, WeatherCache, APILog
)

class SearchHistoryModelTest(TestCase):
    """Test SearchHistory model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_create_search_history(self):
        """Test creating a search history entry"""
        search = SearchHistory.objects.create(
            user=self.user,
            city_name='London',
            country='GB',
            latitude=51.5074,
            longitude=-0.1278,
            ip_address='127.0.0.1',
            user_agent='Mozilla/5.0'
        )
        
        self.assertEqual(search.city_name, 'London')
        self.assertEqual(search.country, 'GB')
        self.assertIsNotNone(search.search_date)
        self.assertEqual(str(search), 'London - {}'.format(search.search_date))
        
    def test_increment_count(self):
        """Test incrementing search count"""
        search = SearchHistory.objects.create(
            user=self.user,
            city_name='Paris',
            country='FR'
        )
        
        self.assertEqual(search.search_count, 1)
        search.increment_count()
        search.refresh_from_db()
        self.assertEqual(search.search_count, 2)

class FavoriteCityModelTest(TestCase):
    """Test FavoriteCity model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_create_favorite(self):
        """Test creating a favorite city"""
        favorite = FavoriteCity.objects.create(
            user=self.user,
            city_name='Tokyo',
            country='JP',
            latitude=35.6762,
            longitude=139.6503,
            notes='Capital of Japan'
        )
        
        self.assertEqual(favorite.city_name, 'Tokyo')
        self.assertEqual(favorite.notes, 'Capital of Japan')
        self.assertTrue(favorite.is_active)
        self.assertEqual(str(favorite), 'testuser - Tokyo')
        
    def test_unique_together(self):
        """Test unique together constraint"""
        FavoriteCity.objects.create(
            user=self.user,
            city_name='New York',
            country='US'
        )
        
        with self.assertRaises(Exception):
            FavoriteCity.objects.create(
                user=self.user,
                city_name='New York',
                country='US'
            )
            
    def test_update_last_accessed(self):
        """Test updating last accessed timestamp"""
        favorite = FavoriteCity.objects.create(
            user=self.user,
            city_name='Sydney',
            country='AU'
        )
        
        old_time = favorite.last_accessed
        favorite.update_last_accessed()
        favorite.refresh_from_db()
        self.assertNotEqual(old_time, favorite.last_accessed)

class WeatherAlertModelTest(TestCase):
    """Test WeatherAlert model"""
    
    def setUp(self):
        self.alert = WeatherAlert.objects.create(
            city_name='Miami',
            country='US',
            latitude=25.7617,
            longitude=-80.1918,
            alert_type='hurricane',
            severity='severe',
            title='Hurricane Warning',
            description='Category 3 hurricane approaching',
            instruction='Evacuate coastal areas',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=2)
        )
        
    def test_create_alert(self):
        """Test creating a weather alert"""
        self.assertEqual(self.alert.alert_type, 'hurricane')
        self.assertEqual(self.alert.severity, 'severe')
        self.assertEqual(str(self.alert), 'Miami - hurricane - {}'.format(self.alert.start_time))
        
    def test_is_active(self):
        """Test alert active status"""
        self.assertTrue(self.alert.is_active())
        
        # Past alert
        past_alert = WeatherAlert.objects.create(
            city_name='Past City',
            country='US',
            alert_type='storm',
            severity='moderate',
            title='Past Alert',
            description='Past event',
            start_time=timezone.now() - timedelta(days=5),
            end_time=timezone.now() - timedelta(days=3)
        )
        self.assertFalse(past_alert.is_active())
        
        # Future alert
        future_alert = WeatherAlert.objects.create(
            city_name='Future City',
            country='US',
            alert_type='storm',
            severity='moderate',
            title='Future Alert',
            description='Future event',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=3)
        )
        self.assertFalse(future_alert.is_active())