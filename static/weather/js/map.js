class WeatherMap {
    constructor() {
        this.mapElement = document.getElementById('weather-map');
        this.infoElement = document.getElementById('map-info');
        this.errorElement = document.getElementById('map-error');
        this.buttonSelector = '.map-btn[data-layer]';
        this.defaultCenter = [20, 0];
        this.defaultZoom = 2;
        this.marker = null;
        this.activeLayerKey = 'temp_new';
        this.weatherApiKey = this.mapElement?.dataset.weatherApiKey || '';
        this.cityLabel = this.mapElement?.dataset.city || '';

        if (!this.mapElement || typeof L === 'undefined') {
            this.renderFatalState('Map library failed to load.');
            return;
        }

        this.init();
    }

    init() {
        this.map = L.map(this.mapElement, {
            zoomControl: true,
        }).setView(this.defaultCenter, this.defaultZoom);

        this.baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19,
        }).addTo(this.map);

        this.weatherLayers = this.createWeatherLayers();
        if (this.weatherLayers[this.activeLayerKey]) {
            this.weatherLayers[this.activeLayerKey].addTo(this.map);
        }
        this.bindControls();
        this.map.on('click', (event) => this.handleMapClick(event.latlng.lat, event.latlng.lng));
        L.control.scale().addTo(this.map);

        this.restoreInitialLocation();
    }

    createWeatherLayers() {
        if (!this.weatherApiKey) {
            return {};
        }

        const layerTypes = {
            temp_new: 'Temperature',
            precipitation_new: 'Precipitation',
            clouds_new: 'Clouds',
            wind_new: 'Wind',
            pressure_new: 'Pressure',
        };

        return Object.fromEntries(Object.entries(layerTypes).map(([layerKey, label]) => [
            layerKey,
            L.tileLayer(`https://tile.openweathermap.org/map/${layerKey}/{z}/{x}/{y}.png?appid=${this.weatherApiKey}`, {
                attribution: `Weather data © OpenWeatherMap - ${label}`,
                opacity: 0.55,
            }),
        ]));
    }

    bindControls() {
        document.querySelectorAll(this.buttonSelector).forEach((button) => {
            button.addEventListener('click', () => {
                const layerKey = button.dataset.layer;
                if (layerKey === 'reset') {
                    this.resetView();
                    return;
                }
                this.switchLayer(layerKey);
            });
        });
    }

    restoreInitialLocation() {
        const params = new URLSearchParams(window.location.search);
        const lat = Number.parseFloat(params.get('lat'));
        const lon = Number.parseFloat(params.get('lon'));
        const city = params.get('city') || this.cityLabel;

        if (Number.isFinite(lat) && Number.isFinite(lon)) {
            this.map.setView([lat, lon], 7);
            this.handleMapClick(lat, lon, city);
            return;
        }

        if (city && this.infoElement) {
            this.infoElement.innerHTML = `<strong>Map ready.</strong> Search results for <strong>${city}</strong> can open here with the same coordinates.`;
        }
    }

    switchLayer(layerKey) {
        document.querySelectorAll(this.buttonSelector).forEach((button) => {
            button.classList.toggle('active', button.dataset.layer === layerKey);
        });

        if (!this.weatherApiKey) {
            this.showNonBlockingError('Weather layers need an OpenWeather API key. The base map is still available.');
            return;
        }

        Object.values(this.weatherLayers).forEach((layer) => {
            if (this.map.hasLayer(layer)) {
                this.map.removeLayer(layer);
            }
        });

        const nextLayer = this.weatherLayers[layerKey];
        if (nextLayer) {
            nextLayer.addTo(this.map);
            this.activeLayerKey = layerKey;
            this.clearError();
        }
    }

    resetView() {
        this.map.setView(this.defaultCenter, this.defaultZoom);
        if (this.marker) {
            this.map.removeLayer(this.marker);
            this.marker = null;
        }
        if (this.infoElement) {
            this.infoElement.innerHTML = '<strong>Click on the map</strong> to inspect weather conditions for that location.';
        }
        this.clearError();
    }

    async handleMapClick(lat, lon, cityLabel = '') {
        this.clearError();
        if (this.infoElement) {
            this.infoElement.innerHTML = `
                <strong>Loading location...</strong><br>
                <span>Lat ${lat.toFixed(4)}, Lon ${lon.toFixed(4)}</span>
            `;
        }

        try {
            const response = await fetch(`/api/v2/weather/current/coords/?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const payload = await response.json();

            if (!response.ok || payload.success === false || !payload.data) {
                throw new Error(payload.error || 'Could not load weather data for this point.');
            }

            const weather = payload.data;
            const title = weather.city || cityLabel || 'Selected location';
            const description = weather.description || 'Unknown conditions';

            this.map.setView([lat, lon], Math.max(this.map.getZoom(), 7));
            if (this.marker) {
                this.map.removeLayer(this.marker);
            }
            this.marker = L.marker([lat, lon]).addTo(this.map);
            this.marker.bindPopup(`
                <strong>${title}</strong><br>
                ${Math.round(weather.temperature ?? 0)}°C<br>
                ${description}
            `).openPopup();

            if (this.infoElement) {
                this.infoElement.innerHTML = `
                    <strong>${title}</strong><br>
                    <span>${Math.round(weather.temperature ?? 0)}°C · ${description}</span><br>
                    <span>Humidity ${weather.humidity ?? 'N/A'}% · Wind ${weather.wind_speed ?? 'N/A'} m/s</span>
                `;
            }
        } catch (error) {
            this.showNonBlockingError(error.message || 'Could not load weather data for this location.');
            if (this.infoElement) {
                this.infoElement.innerHTML = `
                    <strong>Location selected</strong><br>
                    <span>Lat ${lat.toFixed(4)}, Lon ${lon.toFixed(4)}</span><br>
                    <span>Weather details are unavailable right now.</span>
                `;
            }
        }
    }

    showNonBlockingError(message) {
        if (!this.errorElement) {
            return;
        }
        this.errorElement.textContent = message;
        this.errorElement.style.display = 'block';
    }

    clearError() {
        if (!this.errorElement) {
            return;
        }
        this.errorElement.textContent = '';
        this.errorElement.style.display = 'none';
    }

    renderFatalState(message) {
        if (this.errorElement) {
            this.showNonBlockingError(message);
        }
        if (this.mapElement) {
            this.mapElement.innerHTML = `<div class="map-fallback-message">${message}</div>`;
        }
    }
}

window.initWeatherMap = () => new WeatherMap();

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('weather-map')) {
        window.weatherMap = window.initWeatherMap();
    }
});
