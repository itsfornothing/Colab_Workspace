from django.urls import path
from . import views

urlpatterns = [
    # User search
    path("users/search/", views.search_users),

    # Channels
    path("channels/", views.channels),
    path("channels/discover/", views.discover_channels),
    path("channels/<uuid:channel_id>/join/", views.join_channel),
    path("channels/<uuid:channel_id>/leave/", views.leave_channel),
    path("channels/<uuid:channel_id>/messages/", views.channel_messages),
    path("channels/<uuid:channel_id>/upload/", views.upload_channel_file),

    # Direct Messages
    path("dm/", views.dm_conversations),
    path("dm/start/", views.start_dm),
    path("dm/<uuid:conv_id>/messages/", views.dm_messages),
    path("dm/<uuid:conv_id>/send/", views.send_dm),
    path("dm/<uuid:conv_id>/upload/", views.upload_dm_file),

    # Search
    path("messages/search/", views.search_view),

    # Video Call Rooms
    path("rooms/", views.rooms),
    path("rooms/<uuid:room_id>/", views.room_detail),
    path("rooms/<uuid:room_id>/join/", views.join_room),
    path("rooms/<uuid:room_id>/leave/", views.leave_room),
    path("rooms/<uuid:room_id>/invite/", views.invite_to_room),
    path("rooms/<uuid:room_id>/participants/", views.room_participants),
    path("rooms/<uuid:room_id>/participants/<uuid:user_id>/", views.update_participant_state),
    path("call-history/", views.call_history),
    path("ice-servers/", views.ice_servers),

    # Performance monitoring (Requirements 11.1, 11.2, 11.4)
    path("metrics/", views.performance_metrics),
]
