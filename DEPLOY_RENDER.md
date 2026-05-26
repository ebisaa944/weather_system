# Deploying To Render

## 1. Push the repository

Push this project to GitHub first.

## 2. Create services in Render

You can deploy in either of these ways:

- Recommended: use the Blueprint flow and point Render to [render.yaml](/C:/Users/ebisaachame/Desktop/django_tutorial/weather_system/render.yaml)
- Manual: create a Web Service, PostgreSQL database, and Redis instance in the Render dashboard

## 3. Required environment variables

Set these in Render:

- `SECRET_KEY`
- `OPENWEATHER_API_KEY`

Optional:

- `WEATHER_API_KEY`
- `WEATHERAPI_KEY`
- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`

Render will automatically provide:

- `DATABASE_URL`
- `REDIS_URL`
- `RENDER_EXTERNAL_HOSTNAME`

## 4. Build and start commands

- Build: `bash build.sh`
- Pre-deploy: `python manage.py migrate --noinput`
- Start: `gunicorn weather_system.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --threads 2 --timeout 120`

## 5. Post-deploy checks

Verify these URLs:

- `/health/`
- `/`
- `/accounts/login/`
- `/history/`
- `/api/docs/`

## 6. Notes

- Static files are served with WhiteNoise.
- PostgreSQL is used automatically when `DATABASE_URL` is present.
- Render HTTPS works with `RENDER_EXTERNAL_HOSTNAME`, which is automatically trusted by settings.
