"""
Test settings override for integration tests.
Uses SQLite in-memory database and fakeredis for cache/channel layer.
"""
from collaboration_service.settings import *
import fakeredis

# Override database to use SQLite for testing (no PostgreSQL needed)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Override channel layer to use in-memory backend (no Redis needed)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Create a shared fakeredis server for all connections
_FAKE_REDIS_SERVER = fakeredis.FakeServer()

# Override cache to use fakeredis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "REDIS_CLIENT_CLASS": "fakeredis.FakeRedis",
            "REDIS_CLIENT_KWARGS": {"server": _FAKE_REDIS_SERVER},
        },
    }
}

# Ensure SECRET_KEY is set
SECRET_KEY = "test-secret-key-for-integration-tests-only"
DJANGO_SECRET_KEY = SECRET_KEY

# Disable JWT signing key requirement for tests
SIMPLE_JWT = {
    "SIGNING_KEY": "test-jwt-secret-key",
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}
