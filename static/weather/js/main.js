// Main Weather Application JavaScript

class WeatherApp {
    constructor() {
        this.apiEndpoints = {
            current: '/api/v1/weather/current/',
            forecast: '/api/v1/weather/forecast/',
            search: '/api/v1/weather/search/',
            airQuality: '/api/v1/weather/air-quality/',
            geocode: '/api/v1/weather/geocode/',
            reverseGeocode: '/api/v1/weather/reverse-geocode/',
            alerts: '/api/v1/weather/alerts/'
        };
        
        this.state = {
            currentCity: null,
            currentWeather: null,
            forecast: null,
            airQuality: null,
            unit: 'celsius',
            loading: false,
            error: null
        };
        
        this.elements = {};
        this.init();
    }
    
    async init() {
        this.cacheElements();
        this.bindEvents();
        this.loadUserPreferences();
        this.initServiceWorker();
        this.initOfflineDetection();
    }
    
    cacheElements() {
        this.elements = {
            form: document.getElementById('weather-form'),
            cityInput: document.getElementById('city-input'),
            searchBtn: document.getElementById('search-btn'),
            locationBtn: document.getElementById('current-location-btn'),
            weatherResult: document.getElementById('weather-result'),
            errorMessage: document.getElementById('error-message'),
            loadingOverlay: document.getElementById('loading-overlay'),
            suggestionsBox: document.getElementById('suggestions'),
            airQualityCard: document.getElementById('air-quality-card'),
            cityName: document.getElementById('city-name'),
            country: document.getElementById('country'),
            currentDate: document.getElementById('current-date'),
            currentTime: document.getElementById('current-time'),
            weatherIcon: document.getElementById('weather-icon'),
            temperature: document.getElementById('temperature'),
            conditionDescription: document.getElementById('condition-description'),
            feelsLike: document.getElementById('feels-like'),
            weatherDetails: document.getElementById('weather-details'),
            sunrise: document.getElementById('sunrise'),
            sunset: document.getElementById('sunset'),
            dayLength: document.getElementById('day-length'),
            aqiValue: document.getElementById('aqi-value'),
            aqiLabel: document.getElementById('aqi-label'),
            aqiGaugeFill: document.getElementById('aqi-gauge-fill'),
            airQualityComponents: document.getElementById('air-quality-components'),
            forecastContainer: document.getElementById('forecast-container')
        };
    }
    
    bindEvents() {
        // Form submission
        this.elements.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.searchWeather();
        });
        
        // City input with debounce for suggestions
        this.elements.cityInput.addEventListener('input', this.debounce(() => {
            this.getCitySuggestions();
        }, 300));
        
        // Current location button
        this.elements.locationBtn.addEventListener('click', () => {
            this.getCurrentLocation();
        });
        
        // Close suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.elements.cityInput.contains(e.target) && 
                !this.elements.suggestionsBox.contains(e.target)) {
                this.elements.suggestionsBox.style.display = 'none';
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.elements.cityInput.focus();
            }
            
            // Escape to clear search
            if (e.key === 'Escape' && document.activeElement === this.elements.cityInput) {
                this.elements.cityInput.value = '';
                this.elements.cityInput.blur();
            }
        });
        
        // Window resize handler
        window.addEventListener('resize', this.debounce(() => {
            this.handleResize();
        }, 150));
    }
    
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    async getCitySuggestions() {
        const query = this.elements.cityInput.value.trim();
        
        if (query.length < 2) {
            this.elements.suggestionsBox.style.display = 'none';
            return;
        }
        
        try {
            const response = await fetch(`${this.apiEndpoints.search}?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.success && data.data.length > 0) {
                this.displaySuggestions(data.data);
            } else {
                this.elements.suggestionsBox.style.display = 'none';
            }
        } catch (error) {
            console.error('Error fetching suggestions:', error);
        }
    }
    
    displaySuggestions(cities) {
        const suggestionsBox = this.elements.suggestionsBox;
        suggestionsBox.innerHTML = '';
        suggestionsBox.style.display = 'block';
        
        cities.forEach(city => {
            const suggestion = document.createElement('div');
            suggestion.className = 'suggestion-item';
            suggestion.innerHTML = `
                <span class="city-name">${city.name}</span>
                <span class="country">${city.country}</span>
            `;
            
            suggestion.addEventListener('click', () => {
                this.elements.cityInput.value = city.name;
                suggestionsBox.style.display = 'none';
                this.searchWeather();
            });
            
            suggestionsBox.appendChild(suggestion);
        });
    }
    
    async searchWeather() {
        const city = this.elements.cityInput.value.trim();
        
        if (!city) {
            this.showError('Please enter a city name');
            return;
        }
        
        this.showLoading();
        this.hideError();
        
        try {
            // Fetch current weather
            const weatherResponse = await fetch(`${this.apiEndpoints.current}?city=${encodeURIComponent(city)}`);
            const weatherData = await weatherResponse.json();
            
            if (weatherData.success) {
                this.state.currentCity = city;
                this.state.currentWeather = weatherData.data;
                this.displayCurrentWeather(weatherData.data);
                
                // Save to localStorage
                localStorage.setItem('lastCity', city);
                
                // Fetch forecast
                await this.getForecast(city);
                
                // Fetch air quality if coordinates available
                if (weatherData.data.coordinates) {
                    await this.getAirQuality(
                        weatherData.data.coordinates.lat,
                        weatherData.data.coordinates.lon
                    );
                    
                    // Fetch weather alerts
                    await this.getWeatherAlerts(city);
                }
                
                // Update weather animation based on conditions
                this.updateWeatherAnimation(weatherData.data.description);
                
                this.elements.weatherResult.style.display = 'block';
                this.saveSearchHistory(city);
            } else {
                this.showError(weatherData.error || 'Failed to fetch weather data');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showError('An error occurred while fetching weather data');
        } finally {
            this.hideLoading();
        }
    }
    
    displayCurrentWeather(data) {
        // Update basic info
        this.elements.cityName.textContent = data.city;
        this.elements.country.textContent = data.country;
        
        // Update date and time
        const now = new Date();
        this.elements.currentDate.textContent = now.toLocaleDateString('en-US', { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
        this.elements.currentTime.textContent = now.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        // Update weather icon
        if (data.icon) {
            const iconUrl = `https://openweathermap.org/img/wn/${data.icon}@4x.png`;
            this.elements.weatherIcon.src = iconUrl;
            this.elements.weatherIcon.alt = data.description;
        }
        
        // Update temperature
        this.elements.temperature.textContent = Math.round(data.temperature);
        this.elements.conditionDescription.textContent = data.description;
        this.elements.feelsLike.textContent = `Feels like ${Math.round(data.feels_like)}°C`;
        
        // Update weather details
        this.updateWeatherDetails(data);
        
        // Update sun info
        if (data.sunrise && data.sunset) {
            const sunrise = new Date(data.sunrise * 1000);
            const sunset = new Date(data.sunset * 1000);
            const dayLength = new Date(sunset - sunrise);
            
            this.elements.sunrise.textContent = sunrise.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit'
            });
            this.elements.sunset.textContent = sunset.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit'
            });
            this.elements.dayLength.textContent = `${dayLength.getUTCHours()}h ${dayLength.getUTCMinutes()}m`;
        }
    }
    
    updateWeatherDetails(data) {
        const details = [
            { icon: '💧', label: 'Humidity', value: `${data.humidity}%` },
            { icon: '🌬️', label: 'Wind Speed', value: `${data.wind_speed} m/s` },
            { icon: '📊', label: 'Pressure', value: `${data.pressure} hPa` },
            { icon: '☁️', label: 'Clouds', value: `${data.clouds}%` },
            { icon: '👁️', label: 'Visibility', value: `${(data.visibility / 1000).toFixed(1)} km` },
            { icon: '☀️', label: 'UV Index', value: data.uv_index || 'N/A' }
        ];
        
        this.elements.weatherDetails.innerHTML = details.map(detail => `
            <div class="detail-item">
                <span class="detail-icon">${detail.icon}</span>
                <span class="detail-label">${detail.label}</span>
                <span class="detail-value">${detail.value}</span>
            </div>
        `).join('');
    }
    
    async getForecast(city) {
        try {
            const response = await fetch(`${this.apiEndpoints.forecast}?city=${encodeURIComponent(city)}&days=5`);
            const data = await response.json();
            
            if (data.success) {
                this.state.forecast = data.data;
                this.displayForecast(data.data.forecast);
            }
        } catch (error) {
            console.error('Error fetching forecast:', error);
        }
    }
    
    displayForecast(forecast) {
        const container = this.elements.forecastContainer;
        container.innerHTML = '';
        
        forecast.forEach(day => {
            const date = new Date(day.date);
            const card = document.createElement('div');
            card.className = 'forecast-card';
            
            card.innerHTML = `
                <div class="forecast-day">${day.day_name}</div>
                <div class="forecast-date">${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</div>
                <img src="https://openweathermap.org/img/wn/${day.icon}.png" alt="${day.description}" class="forecast-icon">
                <div class="forecast-temp">
                    ${Math.round(day.temp_max)}°<span class="forecast-min">${Math.round(day.temp_min)}°</span>
                </div>
                <div class="forecast-condition">${day.description}</div>
                <div class="forecast-pop">
                    <span>💧</span> ${day.pop}%
                </div>
            `;
            
            card.addEventListener('click', () => {
                this.showForecastDetails(day);
            });
            
            container.appendChild(card);
        });
    }
    
    async getAirQuality(lat, lon) {
        try {
            const response = await fetch(`${this.apiEndpoints.airQuality}?lat=${lat}&lon=${lon}`);
            const data = await response.json();
            
            if (data.success) {
                this.state.airQuality = data.data;
                this.displayAirQuality(data.data);
                this.elements.airQualityCard.style.display = 'block';
            } else {
                this.elements.airQualityCard.style.display = 'none';
            }
        } catch (error) {
            console.error('Error fetching air quality:', error);
            this.elements.airQualityCard.style.display = 'none';
        }
    }
    
    displayAirQuality(data) {
        this.elements.aqiValue.textContent = data.aqi;
        this.elements.aqiLabel.textContent = data.aqi_label;
        
        // Update AQI gauge
        const aqiPercentage = (data.aqi / 5) * 100;
        this.elements.aqiGaugeFill.style.width = `${aqiPercentage}%`;
        
        // Update components
        const components = data.components;
        const componentLabels = {
            co: 'CO',
            no: 'NO',
            no2: 'NO₂',
            o3: 'O₃',
            so2: 'SO₂',
            pm2_5: 'PM2.5',
            pm10: 'PM10',
            nh3: 'NH₃'
        };
        
        this.elements.airQualityComponents.innerHTML = Object.entries(components)
            .filter(([key]) => componentLabels[key])
            .map(([key, value]) => `
                <div class="component-item">
                    <span class="component-name">${componentLabels[key]}</span>
                    <span class="component-value">${value}</span>
                </div>
            `).join('');
    }
    
    async getWeatherAlerts(city) {
        try {
            const response = await fetch(`${this.apiEndpoints.alerts}?city=${encodeURIComponent(city)}`);
            const data = await response.json();
            
            if (data.success && data.data.length > 0) {
                this.displayWeatherAlerts(data.data);
            }
        } catch (error) {
            console.error('Error fetching alerts:', error);
        }
    }
    
    displayWeatherAlerts(alerts) {
        // Create alerts section if it doesn't exist
        let alertsSection = document.getElementById('alerts-section');
        if (!alertsSection) {
            alertsSection = document.createElement('section');
            alertsSection.id = 'alerts-section';
            alertsSection.className = 'alerts-section';
            alertsSection.innerHTML = '<h3 class="section-title"><span class="section-icon">⚠️</span>Weather Alerts</h3>';
            this.elements.weatherResult.appendChild(alertsSection);
        }
        
        const alertsContainer = document.createElement('div');
        alertsContainer.className = 'alerts-container';
        
        alerts.forEach(alert => {
            const alertCard = document.createElement('div');
            alertCard.className = `alert-card alert-${alert.severity}`;
            alertCard.innerHTML = `
                <div class="alert-header">
                    <span class="alert-severity">${alert.severity.toUpperCase()}</span>
                    <span class="alert-source">${alert.source}</span>
                </div>
                <h4 class="alert-title">${alert.title}</h4>
                <p class="alert-description">${alert.description}</p>
                ${alert.instruction ? `<p class="alert-instruction">${alert.instruction}</p>` : ''}
                <div class="alert-times">
                    <span>From: ${new Date(alert.start_time).toLocaleString()}</span>
                    <span>Until: ${new Date(alert.end_time).toLocaleString()}</span>
                </div>
            `;
            alertsContainer.appendChild(alertCard);
        });
        
        alertsSection.appendChild(alertsContainer);
    }
    
    getCurrentLocation() {
        if (!navigator.geolocation) {
            this.showError('Geolocation is not supported by your browser');
            return;
        }
        
        this.showLoading();
        
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                try {
                    const { latitude, longitude } = position.coords;
                    
                    // First reverse geocode to get city name
                    const geoResponse = await fetch(
                        `${this.apiEndpoints.reverseGeocode}?lat=${latitude}&lon=${longitude}`
                    );
                    const geoData = await geoResponse.json();
                    
                    if (geoData.success) {
                        this.elements.cityInput.value = geoData.data.location;
                        await this.searchWeather();
                    } else {
                        // If reverse geocoding fails, use coordinates directly
                        const weatherResponse = await fetch(
                            `${this.apiEndpoints.current}?lat=${latitude}&lon=${longitude}`
                        );
                        const weatherData = await weatherResponse.json();
                        
                        if (weatherData.success) {
                            this.displayCurrentWeather(weatherData.data);
                            this.elements.cityInput.value = weatherData.data.city;
                            this.elements.weatherResult.style.display = 'block';
                        } else {
                            this.showError('Failed to get weather for your location');
                        }
                    }
                } catch (error) {
                    console.error('Error:', error);
                    this.showError('Failed to get weather for your location');
                } finally {
                    this.hideLoading();
                }
            },
            (error) => {
                this.hideLoading();
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        this.showError('Please allow location access to use this feature');
                        break;
                    case error.POSITION_UNAVAILABLE:
                        this.showError('Location information is unavailable');
                        break;
                    case error.TIMEOUT:
                        this.showError('Location request timed out');
                        break;
                    default:
                        this.showError('An unknown error occurred');
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    }
    
    updateWeatherAnimation(condition) {
        const animation = document.getElementById('weather-animation');
        if (!animation) return;
        
        // Remove all weather classes
        animation.className = 'weather-animation';
        
        // Add class based on weather condition
        condition = condition.toLowerCase();
        if (condition.includes('clear') || condition.includes('sunny')) {
            animation.classList.add('sunny');
        } else if (condition.includes('cloud')) {
            animation.classList.add('cloudy');
        } else if (condition.includes('rain') || condition.includes('drizzle')) {
            animation.classList.add('rainy');
        } else if (condition.includes('snow')) {
            animation.classList.add('snowy');
        } else if (condition.includes('thunder') || condition.includes('storm')) {
            animation.classList.add('stormy');
        } else if (condition.includes('fog') || condition.includes('mist')) {
            animation.classList.add('foggy');
        }
    }
    
    saveSearchHistory(city) {
        let history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
        
        // Remove if already exists
        history = history.filter(item => item !== city);
        
        // Add to beginning
        history.unshift(city);
        
        // Keep only last 10
        history = history.slice(0, 10);
        
        localStorage.setItem('searchHistory', JSON.stringify(history));
    }
    
    loadUserPreferences() {
        // Load last searched city
        const lastCity = localStorage.getItem('lastCity');
        if (lastCity) {
            this.elements.cityInput.value = lastCity;
            this.searchWeather();
        }
        
        // Load search history for quick access
        const history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
        this.displaySearchHistory(history);
    }
    
    displaySearchHistory(history) {
        // Create history dropdown if there are items
        if (history.length > 0) {
            // This could be implemented as a dropdown or quick access chips
            console.log('Search history:', history);
        }
    }
    
    showForecastDetails(day) {
        // Create and show modal with detailed forecast
        const modal = document.createElement('div');
        modal.className = 'modal forecast-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${day.day_name} - ${day.date}</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="forecast-details">
                        <div class="detail-row">
                            <span>Temperature:</span>
                            <span>${Math.round(day.temp_min)}°C - ${Math.round(day.temp_max)}°C</span>
                        </div>
                        <div class="detail-row">
                            <span>Humidity:</span>
                            <span>${day.humidity}%</span>
                        </div>
                        <div class="detail-row">
                            <span>Wind Speed:</span>
                            <span>${day.wind_speed} m/s</span>
                        </div>
                        <div class="detail-row">
                            <span>Precipitation:</span>
                            <span>${day.pop}%</span>
                        </div>
                        <div class="detail-row">
                            <span>Condition:</span>
                            <span>${day.description}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close modal
        modal.querySelector('.modal-close').addEventListener('click', () => {
            modal.remove();
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
    
    handleResize() {
        // Adjust UI based on window size
        if (window.innerWidth < 768) {
            // Mobile adjustments
            document.querySelectorAll('.detail-item').forEach(item => {
                item.style.padding = '0.5rem';
            });
        } else {
            // Desktop adjustments
            document.querySelectorAll('.detail-item').forEach(item => {
                item.style.padding = '';
            });
        }
    }
    
    initServiceWorker() {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/weather/js/service-worker.js')
                .then(registration => {
                    console.log('ServiceWorker registered:', registration);
                })
                .catch(error => {
                    console.error('ServiceWorker registration failed:', error);
                });
        }
    }
    
    initOfflineDetection() {
        window.addEventListener('online', () => {
            this.showMessage('You are back online!', 'success');
        });
        
        window.addEventListener('offline', () => {
            this.showMessage('You are offline. Showing cached data.', 'warning');
            this.loadCachedData();
        });
    }
    
    loadCachedData() {
        // Load data from cache when offline
        const lastCity = localStorage.getItem('lastCity');
        if (lastCity) {
            const cachedWeather = localStorage.getItem(`weather_${lastCity}`);
            if (cachedWeather) {
                try {
                    const data = JSON.parse(cachedWeather);
                    this.displayCurrentWeather(data);
                    this.elements.weatherResult.style.display = 'block';
                    this.showMessage('Showing cached weather data', 'info');
                } catch (e) {
                    console.error('Error loading cached data:', e);
                }
            }
        }
    }
    
    showLoading() {
        this.state.loading = true;
        this.elements.loadingOverlay.style.display = 'flex';
        this.elements.searchBtn.disabled = true;
    }
    
    hideLoading() {
        this.state.loading = false;
        this.elements.loadingOverlay.style.display = 'none';
        this.elements.searchBtn.disabled = false;
    }
    
    showError(message) {
        this.state.error = message;
        this.elements.errorMessage.textContent = message;
        this.elements.errorMessage.style.display = 'block';
        
        // Auto hide after 5 seconds
        setTimeout(() => {
            this.hideError();
        }, 5000);
    }
    
    hideError() {
        this.state.error = null;
        this.elements.errorMessage.style.display = 'none';
    }
    
    showMessage(message, type = 'info') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${type}`;
        messageDiv.innerHTML = `
            ${message}
            <button class="message-close">&times;</button>
        `;
        
        document.querySelector('.messages-container').appendChild(messageDiv);
        
        messageDiv.querySelector('.message-close').addEventListener('click', () => {
            messageDiv.remove();
        });
        
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.weatherApp = new WeatherApp();
});