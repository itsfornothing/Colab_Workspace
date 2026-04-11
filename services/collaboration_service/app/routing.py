from django.urls import re_path
from .consumers import DocumentConsumer

websocket_urlpatterns = [
    # paths like /api/ws/docs/... from a reverse proxy prefix.
    re_path(r"^ws/docs/(?P<document_id>[^/]+)/$", DocumentConsumer.as_asgi()),
]