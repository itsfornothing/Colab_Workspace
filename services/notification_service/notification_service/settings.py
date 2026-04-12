"""
Django settings for notification_service project.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv('.env.local')

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1").split(", ")

# BUG FIX: was .split(".") — breaks multi-origin values
CSRF_TRUSTED_ORIGINS = os.getenv(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "https://127.0.0.1"
).split(", ")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'rest_framework',
    'app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'notification_service.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'notification_service.wsgi.application'
ASGI_APPLICATION = "notification_service.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': os.getenv("DATABASE_ENGINE"),
        'NAME': os.getenv("DATABASE_NAME"),
        'USER': os.getenv("DATABASE_USERNAME"),
        'PASSWORD': os.getenv("DATABASE_PASSWORD"),
        'HOST': os.getenv("DATABASE_HOST"),
        'PORT': os.getenv("DATABASE_PORT"),
    }
}

# ---------------------------------------------------------------------------
# Cache (Redis — used for rate limiting and WS session cache)
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_CACHE_URL", "redis://redis:6379/2"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

# ---------------------------------------------------------------------------
# REST Framework + JWT
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    "SIGNING_KEY": os.getenv("JWT_SECRET_KEY"),
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

CELERY_TASK_ROUTES = {
    "app.tasks.process_high_priority": {"queue": "high_priority"},
    "app.tasks.process_low_priority":  {"queue": "low_priority"},
}

CELERY_BEAT_SCHEDULE = {
    # Real-time batch bundler — every 30 seconds
    "batch_notifications": {
        "task": "app.tasks.process_notification_batches",
        "schedule": 30.0,
    },
    # Daily digest — every day at 08:00 UTC
    "daily_digest": {
        "task": "app.tasks.send_daily_digest",
        "schedule": 86400.0,            # crontab(hour=8, minute=0) also works
    },
    # Weekly digest — every Monday at 08:00 UTC
    "weekly_digest": {
        "task": "app.tasks.send_weekly_digest",
        "schedule": 604800.0,
    },
    # Retry failed events — every 5 minutes
    "retry_failed_events": {
        "task": "app.tasks.retry_failed_events",
        "schedule": 300.0,
    },
    # Cleanup old read notifications — daily
    "cleanup_old_notifications": {
        "task": "app.tasks.cleanup_old_notifications",
        "schedule": 86400.0,
    },
}

# ---------------------------------------------------------------------------
# Channel layers
# ---------------------------------------------------------------------------

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.getenv("REDIS_CHANNEL_URL", "redis://redis:6379/3")],
        },
    },
}

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "notifications@yourapp.com")
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "apikey")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# ---------------------------------------------------------------------------
# Firebase
# ---------------------------------------------------------------------------

FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase.json")

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'