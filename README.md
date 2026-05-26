# Weather System

Weather System is a Django app for checking current weather, 5-day forecasts, air quality, alerts, favorites, and user-specific settings from one interface.

## Core features

- Current weather by city and by coordinates
- 5-day forecast
- Air quality lookup
- Weather alerts
- Favorites and search history
- User settings for units, theme, and refresh behavior
- API docs at `/api/docs/`

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Add a `.env` file with at least:

```env
DEBUG=True
SECRET_KEY=change-me
ALLOWED_HOSTS=127.0.0.1,localhost
OPENWEATHER_API_KEY=your_key_here
WEATHERAPI_KEY=your_optional_key_here
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Start the server:

```bash
python manage.py runserver
```

## Notes

- Without live API keys, the app falls back to mock weather data for development.
- For production, configure Redis, email, and background workers for the best experience.
