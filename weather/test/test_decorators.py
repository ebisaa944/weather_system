from django.test import TestCase, RequestFactory
from django.http import JsonResponse
from unittest.mock import patch, MagicMock
from weather.decorators import (
    api_response_time, cache_response, rate_limit,
    validate_city, handle_errors
)

class DecoratorsTest(TestCase):
    """Test custom decorators"""
    
    def setUp(self):
        self.factory = RequestFactory()
        
    def test_api_response_time(self):
        """Test API response time decorator"""
        @api_response_time
        def test_view(request):
            return JsonResponse({'success': True})
            
        request = self.factory.get('/test/')
        response = test_view(request)
        
        self.assertTrue(response.has_header('X-Response-Time'))
        
    @patch('weather.decorators.cache')
    def test_cache_response(self, mock_cache):
        """Test cache response decorator"""
        mock_cache.get.return_value = None
        
        @cache_response(timeout=300)
        def test_view(request):
            return JsonResponse({'success': True})
            
        request = self.factory.get('/test/')
        response = test_view(request)
        
        self.assertEqual(response['X-Cache'], 'MISS')
        
    def test_rate_limit(self):
        """Test rate limit decorator"""
        @rate_limit(key='ip', rate='2/min')
        def test_view(request):
            return JsonResponse({'success': True})
            
        request = self.factory.get('/test/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        
        # First request
        response = test_view(request)
        self.assertEqual(response.status_code, 200)
        
    def test_validate_city(self):
        """Test city validation decorator"""
        @validate_city
        def test_view(request):
            return JsonResponse({'success': True})
            
        # Valid city
        request = self.factory.get('/test/?city=London')
        response = test_view(request)
        self.assertEqual(response.status_code, 200)
        
        # Missing city
        request = self.factory.get('/test/')
        response = test_view(request)
        self.assertEqual(response.status_code, 400)
        
        # Too short city
        request = self.factory.get('/test/?city=L')
        response = test_view(request)
        self.assertEqual(response.status_code, 400)
        
    def test_handle_errors(self):
        """Test error handling decorator"""
        @handle_errors
        def test_view(request):
            raise ValueError('Test error')
            
        request = self.factory.get('/test/')
        response = test_view(request)
        self.assertEqual(response.status_code, 500)