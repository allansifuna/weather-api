#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn weather_api.config.wsgi:application
