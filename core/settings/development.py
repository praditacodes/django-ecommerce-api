"""
Local development defaults: DEBUG on, permissive ALLOWED_HOSTS if unset.
Sets USE_SQLITE_IF_NO_DATABASE_URL when DATABASE_URL is empty.
"""

from .base import *  # noqa

DEBUG = env_bool('DEBUG', True)

if DEBUG and not PUBLIC_SITE_ORIGIN:
    PUBLIC_SITE_ORIGIN = 'http://127.0.0.1:8000'

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Optional: skip Postgres until DATABASE_URL is set
if env_bool('USE_SQLITE_IF_NO_DATABASE_URL', True) and not os.environ.get('DATABASE_URL', '').strip():
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        },
    }

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'CORS_ALLOWED_ORIGINS',
        'http://127.0.0.1:8000',
    ).split(',')
    if origin.strip()
]

CORS_ALLOW_CREDENTIALS = True
