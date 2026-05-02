import uuid
from django.db import models
from django.conf import settings
 
User = settings.AUTH_USER_MODEL
 
 
class UserProfile(models.Model):
    STATUS_CHOICES = [
        ("online",  "Online"),
        ("away",    "Away"),
        ("dnd",     "Do Not Disturb"),
        ("offline", "Offline"),
    ]
 
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    profile_picture = models.URLField(blank=True, null=True)    # Cloudinary URL
    job_title       = models.CharField(max_length=255, blank=True)
    bio             = models.TextField(blank=True)
    # Presence
    online_status   = models.CharField(max_length=10, choices=STATUS_CHOICES, default="offline")
    last_seen       = models.DateTimeField(null=True, blank=True)
    # Notifications
    fcm_token       = models.TextField(blank=True, null=True,
                                       help_text="Firebase Cloud Messaging token for push notifications")
    # Localisation (used by digest scheduler)
    timezone        = models.CharField(max_length=64, default="UTC")
    locale          = models.CharField(max_length=10, default="en")
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        indexes = [models.Index(fields=["user"])]
 
    def __str__(self):
        return f"{self.user} Profile"