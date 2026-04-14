from django.urls import re_path
from .consumers import WebRTCConsumer

websocket_urlpatterns = [
    # Main room signaling channel
    re_path(r"^ws/webrtc/(?P<room_id>[^/]+)/$", WebRTCConsumer.as_asgi()),
]