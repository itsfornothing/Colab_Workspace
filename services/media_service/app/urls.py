from django.urls import path
from .views import (
    create_room,
    get_room,
    end_room,
    get_ice_servers,
    upload_recording_chunk,
    finalize_recording,
    list_recordings,
    create_invite,
    join_via_invite,
)

urlpatterns = [
    # Rooms
    path("rooms/", create_room),                                                  # POST
    path("rooms/<uuid:room_id>/", get_room),                                      # GET
    path("rooms/<uuid:room_id>/end/", end_room),                                  # POST
    path("rooms/<uuid:room_id>/invites/", create_invite),                         # POST
    path("rooms/join/", join_via_invite),                                         # POST

    # ICE servers (STUN/TURN)
    path("ice-servers/", get_ice_servers),                                        # GET

    # Recordings
    path("rooms/<uuid:room_id>/recordings/", list_recordings),                    # GET
    path("rooms/<uuid:room_id>/recordings/chunk/", upload_recording_chunk),       # POST
    path("recordings/<uuid:recording_id>/finalize/", finalize_recording),         # POST
]