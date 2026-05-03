"""
Production-oriented settings — import base and tighten security knobs.
Ensure DEBUG=false, ALLOWED_HOSTS explicit, DATABASE_URL set, HTTPS behind proxy as needed.
"""

import os

from .base import *  # noqa

DEBUG = env_bool('DEBUG', False)

if not ALLOWED_HOSTS:
    raise ValueError(
        'ALLOWED_HOSTS must be set in production (.env): comma-separated hostnames.'
    )

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# When TLS terminates at Nginx, uncomment and tune:
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]

CORS_ALLOW_CREDENTIALS = True

if not PUBLIC_SITE_ORIGIN:
    PUBLIC_SITE_ORIGIN = f'https://{ALLOWED_HOSTS[0]}'
