from django.contrib import admin
from django.utils.html import format_html
from .models import (
    SearchHistory, FavoriteCity, WeatherAlert, 
    UserSettings, WeatherCache, APILog
)

@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('city_name', 'country', 'user', 'search_date', 'search_count')
    list_filter = ('search_date', 'country', 'user')
    search_fields = ('city_name', 'country', 'user__username')
    date_hierarchy = 'search_date'
    readonly_fields = ('ip_address', 'user_agent')
    
    fieldsets = (
        ('Search Information', {
            'fields': ('city_name', 'country', 'latitude', 'longitude')
        }),
        ('User Information', {
            'fields': ('user', 'ip_address', 'user_agent')
        }),
        ('Timing', {
            'fields': ('search_date', 'search_count')
        }),
    )

@admin.register(FavoriteCity)
class FavoriteCityAdmin(admin.ModelAdmin):
    list_display = ('user', 'city_name', 'country', 'added_date', 'last_accessed', 'is_active')
    list_filter = ('is_active', 'added_date', 'country')
    search_fields = ('city_name', 'country', 'user__username')
    readonly_fields = ('added_date', 'last_accessed')
    
    actions = ['mark_active', 'mark_inactive']
    
    def mark_active(self, request, queryset):
        queryset.update(is_active=True)
    mark_active.short_description = "Mark selected as active"
    
    def mark_inactive(self, request, queryset):
        queryset.update(is_active=False)
    mark_inactive.short_description = "Mark selected as inactive"

@admin.register(WeatherAlert)
class WeatherAlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'city_name', 'country', 'alert_type', 'severity', 'start_time', 'end_time', 'alert_status')
    list_filter = ('alert_type', 'severity', 'start_time', 'country')
    search_fields = ('city_name', 'country', 'title', 'description')
    date_hierarchy = 'start_time'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Location', {
            'fields': ('city_name', 'country', 'latitude', 'longitude')
        }),
        ('Alert Details', {
            'fields': ('alert_type', 'severity', 'title', 'description', 'instruction')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'created_at', 'updated_at')
        }),
        ('Source', {
            'fields': ('source', 'external_id')
        }),
    )
    
    def alert_status(self, obj):
        if obj.is_active():
            return format_html('<span style="color: green;">● Active</span>')
        elif obj.end_time < timezone.now():
            return format_html('<span style="color: gray;">● Expired</span>')
        else:
            return format_html('<span style="color: orange;">● Upcoming</span>')
    alert_status.short_description = 'Status'

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'temperature_unit', 'wind_speed_unit', 'theme', 'auto_refresh')
    list_filter = ('temperature_unit', 'wind_speed_unit', 'theme', 'auto_refresh')
    search_fields = ('user__username', 'default_city')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(WeatherCache)
class WeatherCacheAdmin(admin.ModelAdmin):
    list_display = ('cache_key', 'api_source', 'created_at', 'expires_at', 'cache_status')
    list_filter = ('api_source', 'created_at')
    search_fields = ('cache_key',)
    readonly_fields = ('created_at',)
    
    def cache_status(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        else:
            return format_html('<span style="color: green;">Valid</span>')
    cache_status.short_description = 'Status'

@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'method', 'user', 'ip_address', 'response_time', 'status_code', 'timestamp')
    list_filter = ('method', 'status_code', 'timestamp')
    search_fields = ('endpoint', 'user__username', 'ip_address')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False