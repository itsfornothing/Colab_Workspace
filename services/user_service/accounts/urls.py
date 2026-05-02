from django.urls import path
from .views import (
    get_profile, update_profile, public_profile_view,
    update_fcm_token, update_presence, list_users,
)

urlpatterns = [
    path("auth/profile/",                  get_profile),           # GET
    path("auth/profile/update/",           update_profile),        # PATCH
    path("auth/profile/fcm-token/",        update_fcm_token),      # POST
    path("auth/profile/presence/",         update_presence),       # POST
    path("users/",                         list_users),            # GET ?q=
    path("users/<uuid:user_id>/public/",   public_profile_view),   # GET
]