from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, UserSettings

class UserProfileForm(forms.ModelForm):
    """Form for user profile"""
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(required=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'bio', 'location', 'birth_date', 'profile_picture',
            'default_location', 'home_city', 'work_city',
            'notification_email', 'notification_sms', 'notification_push',
            'alert_threshold_temp_high', 'alert_threshold_temp_low',
            'alert_threshold_wind', 'alert_threshold_rain',
            'alert_threshold_snow', 'alert_threshold_aqi',
            'alert_threshold_uv', 'share_weather', 'public_profile'
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Update user info
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            profile.save()
            
        return profile

class UserSettingsForm(forms.ModelForm):
    """Form for user settings"""
    class Meta:
        model = UserSettings
        exclude = ['user', 'created_at', 'updated_at']