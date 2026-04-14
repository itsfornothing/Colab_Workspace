"""
Django settings for media_service project.
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

# BUG FIX: was .split(".") — breaks multi-origin strings
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

ROOT_URLCONF = 'media_service.urls'

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

WSGI_APPLICATION = 'media_service.wsgi.application'
ASGI_APPLICATION = "media_service.asgi.application"

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
# Cache (Redis — WS session auth + rate limiting)
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_CACHE_URL", "redis://redis:6379/2"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

# ---------------------------------------------------------------------------
# Channel layers
# ---------------------------------------------------------------------------

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.getenv("REDIS_CHANNEL_URL", "redis://redis:6379/3")],
            # WebRTC signaling messages are small but latency-sensitive
            "capacity": 1000,
            "expiry": 5,
        },
    },
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
# Celery (recording assembly + housekeeping)
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

CELERY_BEAT_SCHEDULE = {
    "cleanup_inactive_rooms": {
        "task": "app.tasks.cleanup_inactive_rooms",
        "schedule": 300.0,   # every 5 minutes
    },
    "cleanup_old_signals": {
        "task": "app.tasks.cleanup_old_signals",
        "schedule": 86400.0,  # daily
    },
}

# ---------------------------------------------------------------------------
# Media / File storage
# ---------------------------------------------------------------------------

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# Cloud storage (uncomment for production)
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
# AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
# AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
# AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# ---------------------------------------------------------------------------
# TURN server
# ---------------------------------------------------------------------------

# These are read via the IceServer model / admin.
# Set the coturn static-auth-secret here for HMAC credential generation:
TURN_HMAC_SECRET = os.getenv("TURN_HMAC_SECRET", "")

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