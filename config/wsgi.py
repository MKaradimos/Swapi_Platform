"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Defaults to production: this is the entrypoint gunicorn/WSGI servers use,
# and a WSGI deployment should never silently fall back to DEBUG=True.
# setdefault() means an explicit DJANGO_SETTINGS_MODULE env var still wins
# if set — which is why docker-compose.yml also hardcodes this value under
# each service's `environment:` block, so a stray value in .env can't
# override it (see .env.example for details).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()
