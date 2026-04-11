from django.urls import path
from .views import (
    login_view,
    register_view,
    refresh_view,
    logout_view,
    logout_all_view,
    validate_token,
)

urlpatterns = [
    path("auth/register/", register_view),
    path("auth/login/", login_view),
    path("auth/refresh/", refresh_view),
    path("auth/logout/", logout_view),
    path("auth/logout-all/", logout_all_view),
    path("auth/validate/", validate_token),
]