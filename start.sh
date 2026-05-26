#!/usr/bin/env bash
set -o errexit

export DJANGO_SETTINGS_MODULE=weather_system.settings

exec gunicorn weather_system.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers ${WEB_CONCURRENCY:-3} \
  --threads ${GUNICORN_THREADS:-2} \
  --timeout ${GUNICORN_TIMEOUT:-120}
