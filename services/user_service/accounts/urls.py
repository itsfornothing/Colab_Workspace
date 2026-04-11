from django.urls import path
from .views import get_profile, update_profile, public_profile_view

urlpatterns = [
    path("auth/profile/", get_profile),
    path("auth/profile/update/", update_profile),
    path("users/<uuid:user_id>/public/", public_profile_view),
]