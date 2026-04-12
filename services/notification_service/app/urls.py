from django.urls import path
from .views import (
    create_event,
    list_notifications,
    mark_read,
    mark_all_read,
    delete_notification,
    notification_preferences,
)

urlpatterns = [
    # Service-to-service event ingestion
    path("events/", create_event),                                              # POST

    # Notification management
    path("notifications/", list_notifications),                                 # GET
    path("notifications/mark-all-read/", mark_all_read),                        # POST
    path("notifications/preferences/", notification_preferences),               # GET, PUT
    path("notifications/<uuid:notification_id>/read/", mark_read),              # POST
    path("notifications/<uuid:notification_id>/", delete_notification),         # DELETE
]