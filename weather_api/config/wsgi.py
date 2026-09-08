"""WSGI config for weather_api."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "weather_api.config.settings")

application = get_wsgi_application()
