"""
Notification system for weather alerts
"""
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from twilio.rest import Client
import requests
import json
import logging
from .models import Notification, UserProfile, WeatherAlert

logger = logging.getLogger(__name__)

class NotificationService:
    """Handle sending notifications through various channels"""
    
    def __init__(self):
        self.twilio_client = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.twilio_client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            
    def send_email_notification(self, user, title, message):
        """Send email notification"""
        try:
            send_mail(
                subject=f"Weather Alert: {title}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Email sent to {user.email}")
            return True
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return False
            
    def send_sms_notification(self, user, message):
        """Send SMS notification using Twilio"""
        if not self.twilio_client or not hasattr(user, 'profile') or not user.profile.phone_number:
            return False
            
        try:
            message = self.twilio_client.messages.create(
                body=message[:160],  # SMS length limit
                from_=settings.TWILIO_PHONE_NUMBER,
                to=user.profile.phone_number
            )
            logger.info(f"SMS sent to {user.profile.phone_number}")
            return True
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            return False
            
    def send_push_notification(self, user, title, message, data=None):
        """Send push notification using Firebase Cloud Messaging"""
        if not hasattr(user, 'profile') or not user.profile.fcm_token:
            return False
            
        try:
            headers = {
                'Authorization': f'key={settings.FCM_SERVER_KEY}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': user.profile.fcm_token,
                'notification': {
                    'title': title,
                    'body': message,
                    'sound': 'default'
                },
                'data': data or {},
                'priority': 'high'
            }
            
            response = requests.post(
                'https://fcm.googleapis.com/fcm/send',
                headers=headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                logger.info(f"Push notification sent to user {user.id}")
                return True
            else:
                logger.error(f"Push notification failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Push notification error: {e}")
            return False
            
    def check_weather_alerts(self, weather_data, user):
        """Check if weather conditions trigger alerts for user"""
        alerts = []
        
        if not hasattr(user, 'profile'):
            return alerts
            
        profile = user.profile
        
        # Temperature alerts
        if weather_data.get('temperature', 0) > profile.alert_threshold_temp_high:
            alerts.append({
                'type': 'temperature',
                'severity': 'high',
                'title': 'High Temperature Alert',
                'message': f"Temperature of {weather_data['temperature']}°C exceeds your threshold of {profile.alert_threshold_temp_high}°C"
            })
            
        if weather_data.get('temperature', 0) < profile.alert_threshold_temp_low:
            alerts.append({
                'type': 'temperature',
                'severity': 'low',
                'title': 'Low Temperature Alert',
                'message': f"Temperature of {weather_data['temperature']}°C is below your threshold of {profile.alert_threshold_temp_low}°C"
            })
            
        # Wind alert
        if weather_data.get('wind_speed', 0) > profile.alert_threshold_wind:
            alerts.append({
                'type': 'wind',
                'severity': 'high',
                'title': 'High Wind Alert',
                'message': f"Wind speed of {weather_data['wind_speed']} m/s exceeds your threshold of {profile.alert_threshold_wind} m/s"
            })
            
        # Rain alert
        if weather_data.get('rain', {}).get('1h', 0) > profile.alert_threshold_rain:
            alerts.append({
                'type': 'rain',
                'severity': 'moderate',
                'title': 'Heavy Rain Alert',
                'message': f"Rainfall of {weather_data['rain']['1h']} mm exceeds your threshold"
            })
            
        # Snow alert
        if weather_data.get('snow', {}).get('1h', 0) > profile.alert_threshold_snow:
            alerts.append({
                'type': 'snow',
                'severity': 'moderate',
                'title': 'Heavy Snow Alert',
                'message': f"Snowfall of {weather_data['snow']['1h']} mm exceeds your threshold"
            })
            
        # Air quality alert
        if weather_data.get('air_quality', {}).get('aqi', 0) > profile.alert_threshold_aqi:
            alerts.append({
                'type': 'air_quality',
                'severity': 'moderate',
                'title': 'Poor Air Quality Alert',
                'message': f"AQI of {weather_data['air_quality']['aqi']} exceeds your threshold of {profile.alert_threshold_aqi}"
            })
            
        # UV index alert
        if weather_data.get('uv_index', 0) > profile.alert_threshold_uv:
            alerts.append({
                'type': 'uv',
                'severity': 'high',
                'title': 'High UV Index Alert',
                'message': f"UV Index of {weather_data['uv_index']} exceeds your threshold of {profile.alert_threshold_uv}"
            })
            
        return alerts
        
    def process_alerts(self, user, weather_data, city):
        """Process and send alerts for user"""
        alerts = self.check_weather_alerts(weather_data, user)
        
        for alert_data in alerts:
            # Create notification record
            notification = Notification.objects.create(
                user=user,
                notification_type='alert',
                title=alert_data['title'],
                message=alert_data['message'],
                data={
                    'city': city,
                    'weather_data': weather_data,
                    'alert_type': alert_data['type'],
                    'severity': alert_data['severity']
                }
            )
            
            # Send through enabled channels
            profile = user.profile
            
            if profile.notification_email:
                self.send_email_notification(
                    user,
                    alert_data['title'],
                    f"{alert_data['message']}\n\nLocation: {city}\n\nStay safe!"
                )
                
            if profile.notification_sms:
                self.send_sms_notification(
                    user,
                    f"Weather Alert: {alert_data['title']} - {alert_data['message']}"
                )
                
            if profile.notification_push:
                self.send_push_notification(
                    user,
                    alert_data['title'],
                    alert_data['message'],
                    {'city': city, 'type': alert_data['type']}
                )
                
            # Update user stats
            profile.alerts_received += 1
            profile.save()
            
        return alerts