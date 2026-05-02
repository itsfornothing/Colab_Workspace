"""
Django settings for chat_service project.
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

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1").split(",") if h.strip()]

# FIX: was incorrectly split on "." — use "," to match ALLOWED_HOSTS convention
CSRF_TRUSTED_ORIGINS = [h.strip() for h in os.getenv(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "https://127.0.0.1"
).split(",") if h.strip()]

# ---------------------------------------------------------------------------
# Application definition
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

ROOT_URLCONF = 'chat_service.urls'

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

WSGI_APPLICATION = 'chat_service.wsgi.application'

# FIX: defined only once (was duplicated, causing confusion)
ASGI_APPLICATION = 'chat_service.asgi.application'

# ---------------------------------------------------------------------------
# Channel layers (Redis)
# ---------------------------------------------------------------------------

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.environ.get('REDIS_URL', 'redis://localhost:6379/0')],
        },
    },
}

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
# Caches (Redis — separate DB from channel layer)
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ---------------------------------------------------------------------------
# REST Framework + JWT
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'app.auth.ChatJWTAuthentication',
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
# File storage (local for dev — configure Cloudinary in production)
# ---------------------------------------------------------------------------

# DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
# CLOUDINARY_STORAGE = {
#     'CLOUD_NAME': os.getenv("CLOUDINARY_CLOUD_NAME", "your_cloud"),
#     'API_KEY': os.getenv("CLOUDINARY_API_KEY", "your_key"),
#     'API_SECRET': os.getenv("CLOUDINARY_API_SECRET", "your_secret"),
# }

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"
BASE_URL = os.getenv("BASE_URL", "http://localhost:8002")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8000")
WORKSPACE_SERVICE_URL = os.getenv("WORKSPACE_SERVICE_URL", "http://localhost:8001")

# ---------------------------------------------------------------------------
# Firebase (configure in production)
# ---------------------------------------------------------------------------

# FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase.json")

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

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'app.ChatUser'

# ---------------------------------------------------------------------------
# WebRTC Security (Requirement 10.1)
# ---------------------------------------------------------------------------

# DTLS-SRTP: All WebRTC media is automatically encrypted using DTLS-SRTP as
# mandated by the WebRTC specification (RFC 8827). This is enforced by the
# browser's WebRTC implementation — no application-level code is required to
# enable it. Every RTCPeerConnection uses DTLS-SRTP by default.

# WSS (WebSocket Secure): TLS termination is handled at the load balancer /
# reverse-proxy level (e.g. nginx, AWS ALB). The application layer cannot
# reliably enforce WSS because the incoming scope.scheme may appear as "ws"
# even when the client connected over HTTPS/WSS. Set this to True in
# production to enable a warning log when a non-WSS connection is detected.
WEBRTC_REQUIRE_SECURE_SIGNALING = not DEBUG  # True in production, False in development

# WebRTC ICE server configuration (Requirement 10.1)
WEBRTC_ICE_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
]
# Optional TURN server (configure in production for NAT traversal)
# WEBRTC_TURN_SERVER = {
#     "urls": os.getenv("TURN_SERVER_URL", ""),
#     "username": os.getenv("TURN_SERVER_USERNAME", ""),
#     "credential": os.getenv("TURN_SERVER_CREDENTIAL", ""),
# }

# Video call configuration (Requirements 8.1, 6.6)
VIDEO_CALL_MAX_PARTICIPANTS = int(os.getenv("VIDEO_CALL_MAX_PARTICIPANTS", "8"))
VIDEO_CALL_HISTORY_RETENTION_DAYS = int(os.getenv("VIDEO_CALL_HISTORY_RETENTION_DAYS", "90"))
STUN_SERVERS = [
    "stun:stun.l.google.com:19302",
    "stun:stun1.l.google.com:19302",
]

# ---------------------------------------------------------------------------
# Logging — dedicated audit handler for security review (Requirement 10.7)
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'audit': {
            'format': '{asctime} AUDIT {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'audit_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'audit',
        },
    },
    'loggers': {
        'chat_service.audit': {
            'handlers': ['audit_console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}