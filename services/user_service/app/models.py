from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.conf import settings
from django.utils import timezone
from uuid import uuid4


def _default_token():
    return uuid4().hex + uuid4().hex


def _default_short_token():
    return uuid4().hex
 
 
class UserManager(BaseUserManager):
    def create_user(self, email, username, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user  = self.model(id=uuid4(), email=email, username=username,
                           full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
 
    def create_superuser(self, email, username, full_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff",     True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, username, full_name, password, **extra_fields)
 
 
class User(AbstractBaseUser, PermissionsMixin):
    id         = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    email      = models.EmailField(unique=True)
    username   = models.CharField(max_length=100, unique=True)
    full_name  = models.CharField(max_length=255)
    is_active  = models.BooleanField(default=True)
    is_staff   = models.BooleanField(default=False)
    # Email verification
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Profile fields
    job_title = models.CharField(max_length=255, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    avatar_url = models.URLField(max_length=500, blank=True, null=True)

    # Notification preferences
    notification_in_app = models.BooleanField(default=True)
    notification_email = models.BooleanField(default=False)
 
    objects = UserManager()
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["username", "full_name"]
 
    def __str__(self):
        return self.email
 
 
class UserSession(models.Model):
    id            = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name="sessions")
    refresh_token = models.TextField()
    device_info   = models.CharField(max_length=255, blank=True, null=True)
    ip_address    = models.GenericIPAddressField(blank=True, null=True)
    user_agent    = models.TextField(blank=True, null=True)
    expires_at    = models.DateTimeField()
    # Sliding sessions: last_used_at is refreshed on every successful validate
    last_used_at  = models.DateTimeField(default=timezone.now)
    created_at    = models.DateTimeField(auto_now_add=True)
 
    def is_expired(self):
        return self.expires_at < timezone.now()
 
    def __str__(self):
        return f"{self.user} - {self.device_info}"
 
    class Meta:
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["refresh_token"]),
            models.Index(fields=["expires_at"]),
        ]
        # BUG FIX: conditional unique so NULL device_info doesn't cause issues
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_info"],
                condition=models.Q(device_info__isnull=False),
                name="unique_user_device",
            )
        ]
 
 
class TokenBlacklist(models.Model):
    """
    Revoked access tokens. Checked on every /auth/validate/ call.
    Records are pruned once expires_at passes.
    This enables Zero Trust: any issued token can be immediately invalidated.
    """
    jti        = models.CharField(max_length=255, unique=True, db_index=True,
                                  help_text="JWT ID (jti claim) of the revoked token")
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="blacklisted_tokens")
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reason     = models.CharField(max_length=100, blank=True, default="")
 
    class Meta:
        indexes = [models.Index(fields=["jti"]), models.Index(fields=["expires_at"])]
 
    def __str__(self):
        return f"Blacklisted {self.jti} ({self.reason})"
 
 
class SecurityEvent(models.Model):
    EVENT_TYPES = [
        ("login",             "Login"),
        ("logout",            "Logout"),
        ("new_device_login",  "New Device Login"),
        ("suspicious_login",  "Suspicious Login"),
        ("password_change",   "Password Change"),
        ("token_revoked",     "Token Revoked"),
        ("failed_login",      "Failed Login"),
    ]
 
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="security_events")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    metadata   = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
 
    class Meta:
        indexes = [
            models.Index(fields=["user", "event_type"]),
            models.Index(fields=["created_at"]),
        ]
 
 
class PasswordResetToken(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token      = models.CharField(max_length=64, unique=True, db_index=True,
                                  default=_default_token)
    expires_at = models.DateTimeField()
    used       = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
 
    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()
 
 
class EmailVerification(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token      = models.CharField(max_length=64, unique=True, db_index=True,
                                  default=_default_short_token)
    expires_at = models.DateTimeField()
    verified   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)