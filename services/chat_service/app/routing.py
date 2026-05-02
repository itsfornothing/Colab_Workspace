from django.urls import re_path
from .consumers import ChatConsumer, CallConsumer

websocket_urlpatterns = [
    re_path(r"^ws/chat/(?P<channel_id>[^/]+)/$", ChatConsumer.as_asgi()),
    re_path(r"^ws/calls/$", CallConsumer.as_asgi()),
]