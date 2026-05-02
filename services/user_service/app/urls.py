from django.urls import path
from .views import (
    login_view, register_view, refresh_view,
    logout_view, logout_all_view, validate_token,
    revoke_token, list_sessions, delete_session,
    password_reset_request, password_reset_confirm,
    verify_email,
    profile_view, change_password_view,
    notification_preferences_view,
)

urlpatterns = [
    # Core auth
    path("auth/register/",          register_view),
    path("auth/login/",             login_view),
    path("auth/refresh/",           refresh_view),
    path("auth/logout/",            logout_view),
    path("auth/logout-all/",        logout_all_view),
    path("auth/validate/",          validate_token),       # called by Nginx
    path("auth/revoke/",            revoke_token),

    # Profile
    path("auth/profile/",                   profile_view),
    path("auth/profile/update/",            profile_view),   # PATCH
    path("auth/password/change/",           change_password_view),
    path("auth/notification-preferences/",  notification_preferences_view),

    # Sessions
    path("auth/sessions/",                  list_sessions),
    path("auth/sessions/<uuid:session_id>/", delete_session),

    # Password
    path("auth/password/reset/",         password_reset_request),
    path("auth/password/reset/confirm/", password_reset_confirm),

    # Email verification
    path("auth/email/verify/", verify_email),
]