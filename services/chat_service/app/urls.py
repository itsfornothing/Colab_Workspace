from django.urls import path
from services.chat_service.app.views import search_view

urlpatterns = [
    path("messages/search/", search_view),
]