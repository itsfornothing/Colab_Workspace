import uuid
from django.db import models
from django.conf import settings
 
User = settings.AUTH_USER_MODEL
 
 
class Room(models.Model):
    ROOM_TYPES = [
        ("video", "Video"),
        ("audio", "Audio"),
        ("screen", "Screen Share"),
    ]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_rooms"
    )
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default="video")
    is_active = models.BooleanField(default=True)
    is_locked = models.BooleanField(default=False, help_text="Prevent new joins when True")
    max_participants = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        indexes = [
            models.Index(fields=["workspace_id"]),
            models.Index(fields=["is_active"]),
        ]
 
    def __str__(self):
        return f"Room {self.name or self.id} ({self.room_type})"
 
 
class Participant(models.Model):
    ROLE_CHOICES = [
        ("host", "Host"),
        ("co_host", "Co-host"),
        ("participant", "Participant"),
    ]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="media_participations")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="participant")
    is_muted = models.BooleanField(default=False)
    is_video_on = models.BooleanField(default=True)
    is_screen_sharing = models.BooleanField(default=False)
    connection_id = models.CharField(max_length=255, null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        # FIX: removed unique_together — a user may join, leave, and rejoin.
        # Use a conditional partial index in PostgreSQL instead (via migration).
        indexes = [
            models.Index(fields=["room"]),
            models.Index(fields=["user"]),
            models.Index(fields=["room", "left_at"]),  # fast active-participant queries
        ]
 
 
class Signal(models.Model):
    SIGNAL_TYPES = [
        ("offer", "Offer"),
        ("answer", "Answer"),
        ("ice_candidate", "ICE Candidate"),
    ]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="signals")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_signals")
    # Target is a specific peer — NOT a broadcast
    target_user_id = models.UUIDField(db_index=True)
    signal_type = models.CharField(max_length=20, choices=SIGNAL_TYPES)
    signal_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_delivered = models.BooleanField(default=False, db_index=True)
 
    class Meta:
        indexes = [
            models.Index(fields=["room"]),
            models.Index(fields=["target_user_id", "is_delivered"]),
        ]
 
 
class IceServer(models.Model):
    """
    STUN/TURN server configuration.
 
    For TURN servers in production, never store static passwords.
    Use the HMAC-SHA1 mechanism: generate time-limited credentials
    on demand in get_ice_servers_view() using hmac_secret + TTL.
    """
    SERVER_TYPES = [("stun", "STUN"), ("turn", "TURN")]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.CharField(max_length=255, help_text="e.g. turn:coturn.example.com:3478")
    server_type = models.CharField(max_length=10, choices=SERVER_TYPES, default="stun")
 
    # For STUN: leave username/credential blank.
    # For TURN with static auth (dev only):
    username = models.CharField(max_length=255, null=True, blank=True)
    credential = models.CharField(max_length=255, null=True, blank=True)
 
    # For TURN with HMAC time-limited credentials (production):
    hmac_secret = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="coturn static-auth-secret for time-limited HMAC credentials"
    )
    credential_ttl = models.PositiveIntegerField(
        default=86400,
        help_text="TURN credential TTL in seconds (default 24h)"
    )
 
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=0, help_text="Higher = preferred")
 
    class Meta:
        ordering = ["-priority"]
 
 
class Recording(models.Model):
    STATUS_CHOICES = [
        ("recording", "Recording"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="recordings")
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="recordings"
    )
    file_url = models.URLField(null=True, blank=True)
    file_size = models.PositiveBigIntegerField(null=True, blank=True, help_text="Bytes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="recording")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        indexes = [models.Index(fields=["room"])]
 
 
class RecordingChunk(models.Model):
    """
    Stores individual chunks for resumable/chunked recording uploads.
    The recording pipeline assembles these into the final file.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.ForeignKey(
        Recording, on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_index = models.PositiveIntegerField()
    file_url = models.URLField()
    size = models.PositiveBigIntegerField(help_text="Bytes")
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        unique_together = ("recording", "chunk_index")
        ordering = ["chunk_index"]
 
 
class RoomInvite(models.Model):
    """
    Invite link / token for invite-only rooms.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="invites")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    max_uses = models.PositiveIntegerField(default=1)
    use_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
 
    def is_valid(self):
        from django.utils import timezone
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_uses and self.use_count >= self.max_uses:
            return False
        return True