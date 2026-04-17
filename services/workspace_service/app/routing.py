from django.urls import re_path
from .consumers import ChannelConsumer, NotificationConsumer, WorkspaceConsumer

websocket_urlpatterns = [
    # Per-channel WebSocket (replaces workspace-wide broadcast for chat)
    re_path(r"^ws/channels/(?P<channel_id>[^/]+)/$", ChannelConsumer.as_asgi()),
    # Per-user notification stream
    re_path(r"^ws/notifications/$", NotificationConsumer.as_asgi()),
    # Workspace-level events (member joins, role changes, new channels)
    re_path(r"^ws/workspaces/(?P<workspace_id>[^/]+)/$", WorkspaceConsumer.as_asgi()),
]