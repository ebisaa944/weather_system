// Dashboard Management

class DashboardManager {
    constructor() {
        this.init();
    }
    
    async init() {
        this.loadFavoriteCitiesWeather();
        this.loadAlertsPreview();
        this.initCharts();
        this.initRefreshTimers();
    }
    
    async loadFavoriteCitiesWeather() {
        const favoritesList = document.getElementById('favorites-list');
        if (!favoritesList) return;
        
        const favoriteItems = favoritesList.querySelectorAll('.favorite-item');
        
        for (const item of favoriteItems) {
            const city = item.dataset.city;
            await this.updateFavoriteWeather(item, city);
        }
    }
    
    async updateFavoriteWeather(item, city) {
        try {
            const response = await fetch(`/api/v1/weather/current/?city=${encodeURIComponent(city)}`);
            const data = await response.json();
            
            if (data.success) {
                const tempSpan = item.querySelector('.favorite-temp');
                const iconImg = item.querySelector('.favorite-icon');
                
                tempSpan.textContent = `${Math.round(data.data.temperature)}°C`;
                
                if (data.data.icon) {
                    iconImg.src = `https://openweathermap.org/img/wn/${data.data.icon}.png`;
                    iconImg.style.display = 'inline';
                    iconImg.alt = data.data.description;
                }
            }
        } catch (error) {
            console.error(`Error updating weather for ${city}:`, error);
        }
    }
    
    async loadAlertsPreview() {
        const alertsPreview = document.getElementById('alerts-preview');
        if (!alertsPreview) return;
        
        try {
            // Get user's favorite cities for alerts
            const favorites = document.querySelectorAll('.favorite-item');
            const cities = Array.from(favorites).map(item => item.dataset.city);
            
            if (cities.length === 0) {
                alertsPreview.innerHTML = '<p class="empty-message">No active alerts</p>';
                return;
            }
            
            let hasAlerts = false;
            let alertsHtml = '';
            
            for (const city of cities) {
                const response = await fetch(`/api/v1/weather/alerts/?city=${encodeURIComponent(city)}`);
                const data = await response.json();
                
                if (data.success && data.data.length > 0) {
                    hasAlerts = true;
                    alertsHtml += `
                        <div class="alert-preview-item alert-${data.data[0].severity}">
                            <span class="alert-city">${city}</span>
                            <span class="alert-title">${data.data[0].title}</span>
                            <span class="alert-severity">${data.data[0].severity}</span>
                        </div>
                    `;
                }
            }
            
            alertsPreview.innerHTML = hasAlerts ? alertsHtml : '<p class="empty-message">No active alerts</p>';
            
        } catch (error) {
            console.error('Error loading alerts:', error);
            alertsPreview.innerHTML = '<p class="error-message">Failed to load alerts</p>';
        }
    }
    
    initCharts() {
        const chartCanvas = document.getElementById('weather-chart');
        if (!chartCanvas) return;
        
        const citySelect = document.getElementById('chart-city');
        const daysSelect = document.getElementById('chart-days');
        
        if (citySelect) {
            citySelect.addEventListener('change', () => this.updateChart());
        }
        
        if (daysSelect) {
            daysSelect.addEventListener('change', () => this.updateChart());
        }
        
        // Initialize with first city if available
        if (citySelect && citySelect.options.length > 1) {
            this.updateChart();
        }
    }
    
    async updateChart() {
        const citySelect = document.getElementById('chart-city');
        const daysSelect = document.getElementById('chart-days');
        const chartCanvas = document.getElementById('weather-chart');
        
        if (!citySelect || !citySelect.value) return;
        
        const city = citySelect.value;
        const days = daysSelect ? daysSelect.value : 7;
        
        try {
            const response = await fetch(`/api/v1/weather/historical/?city=${encodeURIComponent(city)}&days=${days}`);
            const data = await response.json();
            
            if (data.success) {
                this.renderChart(chartCanvas, data.data);
            }
        } catch (error) {
            console.error('Error loading chart data:', error);
        }
    }
    
    renderChart(canvas, data) {
        if (this.chart) {
            this.chart.destroy();
        }
        
        const dates = data.data.map(item => item.date);
        const maxTemps = data.data.map(item => item.temp_max);
        const minTemps = data.data.map(item => item.temp_min);
        const meanTemps = data.data.map(item => item.temp_mean);
        
        this.chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Max Temperature',
                        data: maxTemps,
                        borderColor: '#f56565',
                        backgroundColor: 'rgba(245, 101, 101, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Mean Temperature',
                        data: meanTemps,
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Min Temperature',
                        data: minTemps,
                        borderColor: '#48bb78',
                        backgroundColor: 'rgba(72, 187, 120, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: 'Temperature Trends'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: 'Temperature (°C)'
                        }
                    }
                }
            }
        });
    }
    
    initRefreshTimers() {
        // Check if auto-refresh is enabled in settings
        const autoRefresh = document.querySelector('[data-auto-refresh="true"]');
        if (autoRefresh) {
            const interval = parseInt(autoRefresh.dataset.refreshInterval || '30') * 1000;
            setInterval(() => {
                this.loadFavoriteCitiesWeather();
                this.loadAlertsPreview();
            }, interval);
        }
    }
    
    // Refresh button handlers
    initRefreshButtons() {
        document.querySelectorAll('.favorite-refresh').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const city = btn.dataset.city;
                const item = btn.closest('.favorite-item');
                this.updateFavoriteWeather(item, city);
            });
        });
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.dashboard-container')) {
        window.dashboardManager = new DashboardManager();
    }
});