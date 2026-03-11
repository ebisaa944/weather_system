from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import json

class SearchHistory(models.Model):
    """Store user search history"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    city_name = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    search_date = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    search_count = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['-search_date']
        indexes = [
            models.Index(fields=['user', '-search_date']),
            models.Index(fields=['city_name', 'country']),
        ]
    
    def __str__(self):
        return f"{self.city_name} - {self.search_date}"
    
    def increment_count(self):
        self.search_count += 1
        self.save()

class FavoriteCity(models.Model):
    """Store user favorite cities"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    city_name = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    added_date = models.DateTimeField(default=timezone.now)
    last_accessed = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['user', 'city_name']
        ordering = ['city_name']
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.city_name}"
    
    def update_last_accessed(self):
        self.last_accessed = timezone.now()
        self.save()

class WeatherAlert(models.Model):
    """Weather alerts for locations"""
    ALERT_TYPES = [
        ('storm', 'Thunderstorm'),
        ('tornado', 'Tornado'),
        ('hurricane', 'Hurricane'),
        ('flood', 'Flood'),
        ('extreme_temp', 'Extreme Temperature'),
        ('high_wind', 'High Wind'),
        ('heavy_snow', 'Heavy Snow'),
        ('blizzard', 'Blizzard'),
        ('fog', 'Dense Fog'),
        ('heat', 'Heat Wave'),
        ('cold', 'Cold Wave'),
        ('fire', 'Fire Danger'),
        ('avalanche', 'Avalanche'),
        ('other', 'Other'),
    ]
    
    SEVERITY_LEVELS = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe'),
        ('extreme', 'Extreme'),
    ]
    
    city_name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    title = models.CharField(max_length=200)
    description = models.TextField()
    instruction = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    source = models.CharField(max_length=100, blank=True)
    external_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['city_name', 'country']),
            models.Index(fields=['-start_time']),
            models.Index(fields=['severity']),
        ]
    
    def __str__(self):
        return f"{self.city_name} - {self.alert_type} - {self.start_time}"
    
    def is_active(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time

class UserSettings(models.Model):
    """User preferences and settings"""
    TEMP_UNITS = [
        ('celsius', 'Celsius (°C)'),
        ('fahrenheit', 'Fahrenheit (°F)'),
    ]
    
    SPEED_UNITS = [
        ('metric', 'm/s'),
        ('imperial', 'mph'),
    ]
    
    TIME_FORMATS = [
        ('12h', '12-hour'),
        ('24h', '24-hour'),
    ]
    
    THEMES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto (System)'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='weather_settings')
    temperature_unit = models.CharField(max_length=10, choices=TEMP_UNITS, default='celsius')
    wind_speed_unit = models.CharField(max_length=10, choices=SPEED_UNITS, default='metric')
    time_format = models.CharField(max_length=3, choices=TIME_FORMATS, default='24h')
    theme = models.CharField(max_length=10, choices=THEMES, default='auto')
    
    # Notification preferences
    email_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=False)
    alert_threshold = models.CharField(max_length=10, default='moderate')
    
    # Default locations
    default_city = models.CharField(max_length=100, blank=True)
    default_country = models.CharField(max_length=100, blank=True)
    
    # Display preferences
    show_map = models.BooleanField(default=True)
    show_air_quality = models.BooleanField(default=True)
    show_alerts = models.BooleanField(default=True)
    auto_refresh = models.BooleanField(default=False)
    refresh_interval = models.IntegerField(default=30, validators=[MinValueValidator(5), MaxValueValidator(360)])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s settings"

class WeatherCache(models.Model):
    """Cache for weather API responses"""
    cache_key = models.CharField(max_length=255, unique=True, db_index=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    api_source = models.CharField(max_length=50)
    
    class Meta:
        indexes = [
            models.Index(fields=['cache_key', 'expires_at']),
        ]
    
    def __str__(self):
        return f"Cache: {self.cache_key}"
    
    def is_expired(self):
        return timezone.now() > self.expires_at

class APILog(models.Model):
    """Log API requests for monitoring"""
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    response_time = models.FloatField(help_text="Response time in seconds")
    status_code = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['endpoint', 'status_code']),
        ]