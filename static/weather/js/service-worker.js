const CACHE_NAME = 'weather-app-v1';
const urlsToCache = [
    '/',
    '/static/weather/css/style.css',
    '/static/weather/css/themes.css',
    '/static/weather/css/dashboard.css',
    '/static/weather/js/main.js',
    '/static/weather/js/theme.js',
    '/static/weather/js/dashboard.js',
    '/static/weather/js/charts.js',
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap'
];

// Install service worker
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Opened cache');
                return cache.addAll(urlsToCache);
            })
    );
});

// Cache and return requests
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Cache hit - return response
                if (response) {
                    return response;
                }
                
                // Clone the request
                const fetchRequest = event.request.clone();
                
                return fetch(fetchRequest).then(
                    response => {
                        // Check if valid response
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            return response;
                        }
                        
                        // Clone the response
                        const responseToCache = response.clone();
                        
                        caches.open(CACHE_NAME)
                            .then(cache => {
                                // Don't cache API responses
                                if (!event.request.url.includes('/api/')) {
                                    cache.put(event.request, responseToCache);
                                }
                            });
                        
                        return response;
                    }
                );
            })
    );
});

// Update service worker
self.addEventListener('activate', event => {
    const cacheWhitelist = [CACHE_NAME];
    
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheWhitelist.indexOf(cacheName) === -1) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

// Handle offline analytics
self.addEventListener('sync', event => {
    if (event.tag === 'weather-sync') {
        event.waitUntil(syncWeatherData());
    }
});

async function syncWeatherData() {
    // Sync cached weather data when back online
    const cache = await caches.open(CACHE_NAME);
    const keys = await cache.keys();
    
    // Find and update weather data
    for (const request of keys) {
        if (request.url.includes('/api/weather/')) {
            try {
                const response = await fetch(request);
                if (response.ok) {
                    await cache.put(request, response);
                }
            } catch (error) {
                console.error('Error syncing:', error);
            }
        }
    }
}

// Push notification handling
self.addEventListener('push', event => {
    const data = event.data.json();
    
    const options = {
        body: data.body,
        icon: '/static/weather/images/icon-192x192.png',
        badge: '/static/weather/images/badge-72x72.png',
        vibrate: [200, 100, 200],
        data: {
            url: data.url
        },
        actions: [
            {
                action: 'view',
                title: 'View Details'
            },
            {
                action: 'close',
                title: 'Close'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Notification click handling
self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    if (event.action === 'view') {
        event.waitUntil(
            clients.openWindow(event.notification.data.url)
        );
    }
});