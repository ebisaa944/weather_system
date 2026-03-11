from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    SearchHistory, FavoriteCity, WeatherAlert, 
    UserSettings, WeatherCache
)
import json

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']

class SearchHistorySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = SearchHistory
        fields = [
            'id', 'city_name', 'country', 'latitude', 'longitude',
            'search_date', 'search_count'
        ]
        read_only_fields = ['id', 'search_date', 'search_count']

class FavoriteCitySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = FavoriteCity
        fields = [
            'id', 'city_name', 'country', 'latitude', 'longitude',
            'added_date', 'last_accessed', 'notes', 'is_active'
        ]
        read_only_fields = ['id', 'added_date', 'last_accessed']

class WeatherAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherAlert
        fields = [
            'id', 'city_name', 'country', 'latitude', 'longitude',
            'alert_type', 'severity', 'title', 'description',
            'instruction', 'start_time', 'end_time', 'source'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError(
                "End time must be after start time"
            )
        return data

class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            'temperature_unit', 'wind_speed_unit', 'time_format',
            'theme', 'email_notifications', 'push_notifications',
            'alert_threshold', 'default_city', 'default_country',
            'show_map', 'show_air_quality', 'show_alerts',
            'auto_refresh', 'refresh_interval'
        ]
    
    def validate_refresh_interval(self, value):
        if value < 5 or value > 360:
            raise serializers.ValidationError(
                "Refresh interval must be between 5 and 360 seconds"
            )
        return value

class CurrentWeatherSerializer(serializers.Serializer):
    """Serializer for current weather data"""
    city = serializers.CharField()
    country = serializers.CharField()
    temperature = serializers.FloatField()
    feels_like = serializers.FloatField()
    humidity = serializers.IntegerField()
    pressure = serializers.IntegerField()
    description = serializers.CharField()
    icon = serializers.CharField()
    wind_speed = serializers.FloatField()
    wind_direction = serializers.IntegerField(allow_null=True)
    clouds = serializers.IntegerField()
    visibility = serializers.FloatField(allow_null=True)
    sunrise = serializers.DateTimeField()
    sunset = serializers.DateTimeField()
    uv_index = serializers.FloatField(allow_null=True)
    air_quality = serializers.DictField(allow_null=True)
    
    class Meta:
        fields = '__all__'

class ForecastSerializer(serializers.Serializer):
    """Serializer for forecast data"""
    date = serializers.DateField()
    day_name = serializers.CharField()
    temp_min = serializers.FloatField()
    temp_max = serializers.FloatField()
    humidity = serializers.IntegerField()
    description = serializers.CharField()
    icon = serializers.CharField()
    wind_speed = serializers.FloatField()
    pop = serializers.IntegerField()  # Probability of precipitation
    
    class Meta:
        fields = '__all__'

class AirQualitySerializer(serializers.Serializer):
    """Serializer for air quality data"""
    aqi = serializers.IntegerField()
    aqi_label = serializers.CharField()
    components = serializers.DictField()
    
    class Meta:
        fields = '__all__'

class WeatherStatisticsSerializer(serializers.Serializer):
    """Serializer for weather statistics"""
    city = serializers.CharField()
    average_temp = serializers.FloatField()
    average_humidity = serializers.FloatField()
    rainy_days_per_month = serializers.IntegerField()
    sunny_days_per_month = serializers.IntegerField()
    best_time_to_visit = serializers.CharField()
    climate = serializers.CharField()
    
    class Meta:
        fields = '__all__'