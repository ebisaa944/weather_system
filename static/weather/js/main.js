class WeatherApp {
    constructor() {
        this.apiEndpoints = {
            current: '/api/v2/weather/current/',
            currentByCoords: '/api/v2/weather/current/coords/',
            forecast: '/api/v2/weather/forecast/',
            search: '/api/v2/weather/search/',
            airQuality: '/api/v2/weather/air-quality/',
            reverseGeocode: '/api/v2/weather/reverse-geocode/',
            alerts: '/api/v2/weather/alerts/',
        };

        this.state = {
            city: null,
            currentWeather: null,
            forecast: [],
        };

        this.elements = {};
        this.init();
    }

    init() {
        this.cacheElements();
        if (!this.elements.form) {
            return;
        }
        this.bindEvents();
        this.restoreLastCity();
    }

    cacheElements() {
        this.elements = {
            form: document.getElementById('weather-form'),
            cityInput: document.getElementById('city-input'),
            searchBtn: document.getElementById('search-btn'),
            locationBtn: document.getElementById('current-location-btn'),
            suggestionsBox: document.getElementById('suggestions'),
            loadingOverlay: document.getElementById('loading-overlay'),
            weatherResult: document.getElementById('weather-result'),
            errorMessage: document.getElementById('error-message'),
            heroMapLink: document.getElementById('hero-map-link'),
            mapPreviewLink: document.getElementById('map-preview-link'),
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
            forecastContainer: document.getElementById('forecast-container'),
            airQualityCard: document.getElementById('air-quality-card'),
            aqiValue: document.getElementById('aqi-value'),
            aqiLabel: document.getElementById('aqi-label'),
            aqiGaugeFill: document.getElementById('aqi-gauge-fill'),
            airQualityComponents: document.getElementById('air-quality-components'),
        };
    }

    bindEvents() {
        this.elements.form.addEventListener('submit', (event) => {
            event.preventDefault();
            this.searchWeather();
        });

        if (this.elements.cityInput) {
            this.elements.cityInput.addEventListener('input', this.debounce(() => {
                this.getCitySuggestions();
            }, 250));
        }

        if (this.elements.locationBtn) {
            this.elements.locationBtn.addEventListener('click', () => this.getCurrentLocation());
        }

        document.addEventListener('click', (event) => {
            const input = this.elements.cityInput;
            const suggestions = this.elements.suggestionsBox;
            if (!input || !suggestions) {
                return;
            }
            if (!input.contains(event.target) && !suggestions.contains(event.target)) {
                suggestions.style.display = 'none';
            }
        });
    }

    debounce(callback, wait) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => callback(...args), wait);
        };
    }

    async fetchJson(url) {
        const response = await fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        });
        const payload = await response.json();
        if (!response.ok || payload.success === false) {
            throw new Error(payload.error || `Request failed with ${response.status}`);
        }
        return payload;
    }

    async getCitySuggestions() {
        const query = (this.elements.cityInput?.value || '').trim();
        if (query.length < 2) {
            this.hideSuggestions();
            return;
        }

        try {
            const payload = await this.fetchJson(`${this.apiEndpoints.search}?q=${encodeURIComponent(query)}`);
            this.displaySuggestions(payload.data || []);
        } catch (error) {
            this.hideSuggestions();
        }
    }

    displaySuggestions(cities) {
        const box = this.elements.suggestionsBox;
        if (!box) {
            return;
        }

        if (!cities.length) {
            this.hideSuggestions();
            return;
        }

        box.innerHTML = '';
        cities.forEach((city) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'suggestion-item';
            item.innerHTML = `<span class="city-name">${city.name}</span><span class="country">${city.country || ''}</span>`;
            item.addEventListener('click', () => this.selectCity(city.name));
            box.appendChild(item);
        });
        box.style.display = 'block';
    }

    hideSuggestions() {
        if (this.elements.suggestionsBox) {
            this.elements.suggestionsBox.style.display = 'none';
        }
    }

    selectCity(city) {
        if (this.elements.cityInput) {
            this.elements.cityInput.value = city;
        }
        this.hideSuggestions();
        this.searchWeather();
    }

    async searchWeather(city = null) {
        const targetCity = city || (this.elements.cityInput?.value || '').trim();
        if (!targetCity) {
            this.showError('Please enter a city name.');
            return;
        }

        this.showLoading();
        this.hideError();

        try {
            const currentPayload = await this.fetchJson(`${this.apiEndpoints.current}?city=${encodeURIComponent(targetCity)}`);
            const weatherData = currentPayload.data;
            this.state.city = targetCity;
            this.state.currentWeather = weatherData;
            this.displayCurrentWeather(weatherData);
            this.updateMapLinks(weatherData, targetCity);
            this.cacheWeather(targetCity, weatherData);
            localStorage.setItem('lastCity', targetCity);

            const tasks = [
                this.loadForecast(targetCity),
            ];

            const coords = weatherData.coordinates || {};
            if (typeof coords.lat === 'number' && typeof coords.lon === 'number') {
                tasks.push(this.loadAirQuality(coords.lat, coords.lon));
            } else {
                this.hideAirQuality();
            }

            await Promise.allSettled(tasks);
            this.elements.weatherResult.style.display = 'block';
        } catch (error) {
            this.showError(error.message || 'Unable to load weather data.');
        } finally {
            this.hideLoading();
        }
    }

    async loadForecast(city) {
        const payload = await this.fetchJson(`${this.apiEndpoints.forecast}?city=${encodeURIComponent(city)}&days=5`);
        this.state.forecast = payload.data?.forecast || [];
        this.displayForecast(this.state.forecast);
    }

    async searchWeatherByCoords(lat, lon) {
        this.showLoading();
        this.hideError();

        try {
            const currentPayload = await this.fetchJson(`${this.apiEndpoints.currentByCoords}?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`);
            const weatherData = currentPayload.data;
            const resolvedCity = weatherData.city || 'Current location';

            this.state.city = resolvedCity;
            this.state.currentWeather = weatherData;

            if (this.elements.cityInput) {
                this.elements.cityInput.value = resolvedCity;
            }

            this.displayCurrentWeather(weatherData);
            this.updateMapLinks(weatherData, resolvedCity);
            this.cacheWeather(resolvedCity, weatherData);
            localStorage.setItem('lastCity', resolvedCity);
            this.elements.weatherResult.style.display = 'block';

            const tasks = [this.loadAirQuality(lat, lon)];
            if (weatherData.city) {
                tasks.push(this.loadForecast(weatherData.city));
            } else {
                this.displayForecast([]);
            }

            try {
                const reversePayload = await this.fetchJson(`${this.apiEndpoints.reverseGeocode}?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`);
                const locationName = reversePayload.data?.location;
                if (locationName && locationName !== 'Current location' && this.elements.cityInput) {
                    this.elements.cityInput.value = locationName;
                }
            } catch (error) {
                // Weather-by-coordinates already succeeded, so we can safely ignore reverse geocode failures.
            }

            await Promise.allSettled(tasks);
        } catch (error) {
            this.showError(error.message || 'Unable to load weather data for your location.');
        } finally {
            this.hideLoading();
        }
    }

    async loadAirQuality(lat, lon) {
        try {
            const payload = await this.fetchJson(`${this.apiEndpoints.airQuality}?lat=${lat}&lon=${lon}`);
            this.displayAirQuality(payload.data || {});
        } catch (error) {
            this.hideAirQuality();
        }
    }

    displayCurrentWeather(data) {
        this.elements.cityName.textContent = data.city || 'Unknown';
        this.elements.country.textContent = data.country || '';

        const now = new Date();
        this.elements.currentDate.textContent = now.toLocaleDateString(undefined, {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
        });
        this.elements.currentTime.textContent = now.toLocaleTimeString(undefined, {
            hour: '2-digit',
            minute: '2-digit',
        });

        if (data.icon) {
            this.elements.weatherIcon.src = `https://openweathermap.org/img/wn/${data.icon}@4x.png`;
            this.elements.weatherIcon.alt = data.description || 'Weather icon';
        }

        this.elements.temperature.textContent = Math.round(data.temperature ?? 0);
        this.elements.conditionDescription.textContent = data.description || 'Unknown conditions';
        this.elements.feelsLike.textContent = `Feels like ${Math.round(data.feels_like ?? data.temperature ?? 0)}°C`;

        const visibility = typeof data.visibility === 'number'
            ? `${(data.visibility / 1000).toFixed(data.visibility % 1000 === 0 ? 0 : 1)} km`
            : 'N/A';

        const details = [
            { label: 'Humidity', value: `${data.humidity ?? 'N/A'}%` },
            { label: 'Wind', value: `${data.wind_speed ?? 'N/A'} m/s` },
            { label: 'Pressure', value: `${data.pressure ?? 'N/A'} hPa` },
            { label: 'Cloud Cover', value: `${data.clouds ?? 'N/A'}%` },
            { label: 'Visibility', value: visibility },
            { label: 'UV Index', value: data.uv_index ?? 'N/A' },
        ];

        this.elements.weatherDetails.innerHTML = details.map((detail) => `
            <div class="detail-item">
                <span class="detail-label">${detail.label}</span>
                <span class="detail-value">${detail.value}</span>
            </div>
        `).join('');

        this.updateSunInfo(data.sunrise, data.sunset);
        this.updateWeatherAnimation(data.description || '');
    }

    updateSunInfo(sunriseTimestamp, sunsetTimestamp) {
        if (!sunriseTimestamp || !sunsetTimestamp) {
            this.elements.sunrise.textContent = 'N/A';
            this.elements.sunset.textContent = 'N/A';
            this.elements.dayLength.textContent = 'N/A';
            return;
        }

        const sunrise = new Date(sunriseTimestamp * 1000);
        const sunset = new Date(sunsetTimestamp * 1000);
        const dayLengthMs = sunset.getTime() - sunrise.getTime();
        const daylightHours = Math.floor(dayLengthMs / (1000 * 60 * 60));
        const daylightMinutes = Math.round((dayLengthMs % (1000 * 60 * 60)) / (1000 * 60));

        this.elements.sunrise.textContent = sunrise.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
        this.elements.sunset.textContent = sunset.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
        this.elements.dayLength.textContent = `${daylightHours}h ${daylightMinutes}m`;
    }

    displayForecast(forecast) {
        if (!this.elements.forecastContainer) {
            return;
        }
        if (!forecast.length) {
            this.elements.forecastContainer.innerHTML = `
                <article class="forecast-card forecast-card-empty">
                    <div class="forecast-day">Forecast unavailable</div>
                    <div class="forecast-condition">We could not load a 5-day outlook for this location yet.</div>
                </article>
            `;
            return;
        }
        this.elements.forecastContainer.innerHTML = forecast.map((day) => `
            <article class="forecast-card">
                <div class="forecast-day">${day.day_name}</div>
                <div class="forecast-date">${new Date(day.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</div>
                <img class="forecast-icon" src="https://openweathermap.org/img/wn/${day.icon}.png" alt="${day.description}">
                <div class="forecast-temp">${Math.round(day.temp_max)}° <span class="forecast-min">${Math.round(day.temp_min)}°</span></div>
                <div class="forecast-condition">${day.description}</div>
                <div class="forecast-pop">Rain chance ${day.pop ?? 0}%</div>
            </article>
        `).join('');
    }

    displayAirQuality(data) {
        if (!this.elements.airQualityCard) {
            return;
        }
        this.elements.airQualityCard.style.display = 'block';
        this.elements.aqiValue.textContent = data.aqi ?? 'N/A';
        this.elements.aqiLabel.textContent = data.aqi_label || 'Unknown';
        this.elements.aqiGaugeFill.style.width = `${Math.max(0, Math.min(100, ((data.aqi || 1) / 5) * 100))}%`;

        const labelMap = {
            co: 'CO',
            no: 'NO',
            no2: 'NO2',
            o3: 'O3',
            so2: 'SO2',
            pm2_5: 'PM2.5',
            pm10: 'PM10',
            nh3: 'NH3',
        };

        this.elements.airQualityComponents.innerHTML = Object.entries(data.components || {}).map(([key, value]) => `
            <div class="component-item">
                <span class="component-name">${labelMap[key] || key}</span>
                <span class="component-value">${value}</span>
            </div>
        `).join('');
    }

    hideAirQuality() {
        if (this.elements.airQualityCard) {
            this.elements.airQualityCard.style.display = 'none';
        }
    }

    getCurrentLocation() {
        if (!window.isSecureContext) {
            this.showError('Location access only works on HTTPS or http://localhost. Open the app on localhost or enable HTTPS and try again.');
            return;
        }

        if (!navigator.geolocation) {
            this.showError('Your browser does not support location access.');
            return;
        }

        this.showLoading();
        this.hideError();
        navigator.geolocation.getCurrentPosition(async (position) => {
            try {
                const { latitude, longitude } = position.coords;
                await this.searchWeatherByCoords(latitude, longitude);
            } catch (error) {
                this.showError('Unable to determine your location.');
                this.hideLoading();
            }
        }, (error) => {
            switch (error.code) {
                case error.PERMISSION_DENIED:
                    this.showError('Location access was denied. Allow location permission in your browser and try again.');
                    break;
                case error.POSITION_UNAVAILABLE:
                    this.showError('Your device could not determine your location. Check location services and try again.');
                    break;
                case error.TIMEOUT:
                    this.showError('Location lookup timed out. Try again where your device has a stronger location signal.');
                    break;
                default:
                    this.showError('Unable to determine your location.');
                    break;
            }
            this.hideLoading();
        }, {
            enableHighAccuracy: true,
            timeout: 10000,
        });
    }

    updateWeatherAnimation(description) {
        const animation = document.getElementById('weather-animation');
        if (!animation) {
            return;
        }
        animation.className = 'weather-animation';
        const normalized = description.toLowerCase();
        if (normalized.includes('rain') || normalized.includes('storm')) {
            animation.classList.add('rainy');
        } else if (normalized.includes('cloud')) {
            animation.classList.add('cloudy');
        } else if (normalized.includes('snow')) {
            animation.classList.add('snowy');
        } else {
            animation.classList.add('sunny');
        }
    }

    updateMapLinks(weatherData, cityLabel = '') {
        const coords = weatherData?.coordinates || {};
        const url = new URL('/map/', window.location.origin);
        const city = weatherData?.city || cityLabel;

        if (typeof coords.lat === 'number' && typeof coords.lon === 'number') {
            url.searchParams.set('lat', coords.lat);
            url.searchParams.set('lon', coords.lon);
        }

        if (city) {
            url.searchParams.set('city', city);
        }

        [this.elements.heroMapLink, this.elements.mapPreviewLink].forEach((link) => {
            if (link) {
                link.href = url.pathname + url.search;
            }
        });
    }

    cacheWeather(city, data) {
        try {
            localStorage.setItem(`weather_${city.toLowerCase()}`, JSON.stringify(data));
        } catch (error) {
            // Ignore cache issues silently.
        }
    }

    restoreLastCity() {
        const urlParams = new URLSearchParams(window.location.search);
        const cityFromUrl = urlParams.get('city');
        const lastCity = cityFromUrl || localStorage.getItem('lastCity');
        this.updateMapLinks({}, lastCity || '');
        if (lastCity && this.elements.cityInput) {
            this.elements.cityInput.value = lastCity;
            if (cityFromUrl) {
                this.searchWeather(lastCity);
            }
        }
    }

    showLoading() {
        if (this.elements.loadingOverlay) {
            this.elements.loadingOverlay.style.display = 'flex';
        }
        if (this.elements.searchBtn) {
            this.elements.searchBtn.disabled = true;
        }
        if (this.elements.locationBtn) {
            this.elements.locationBtn.disabled = true;
        }
    }

    hideLoading() {
        if (this.elements.loadingOverlay) {
            this.elements.loadingOverlay.style.display = 'none';
        }
        if (this.elements.searchBtn) {
            this.elements.searchBtn.disabled = false;
        }
        if (this.elements.locationBtn) {
            this.elements.locationBtn.disabled = false;
        }
    }

    showError(message) {
        if (!this.elements.errorMessage) {
            return;
        }
        this.elements.errorMessage.textContent = message;
        this.elements.errorMessage.style.display = 'block';
    }

    hideError() {
        if (this.elements.errorMessage) {
            this.elements.errorMessage.style.display = 'none';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.weatherApp = new WeatherApp();
    window.searchWeather = () => window.weatherApp?.searchWeather();
    window.getCurrentLocation = () => window.weatherApp?.getCurrentLocation();
    window.selectCity = (city) => window.weatherApp?.selectCity(city);
});
