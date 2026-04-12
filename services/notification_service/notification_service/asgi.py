"""
ASGI config for notification_service project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

"""
ASGI config for notification_service.

BUG FIX: Original had no authentication middleware on WebSocket route.
JWTAuthMiddleware now wraps the URLRouter.
"""

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from .middleware import JWTAuthMiddleware
from app.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "notification_service.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})
