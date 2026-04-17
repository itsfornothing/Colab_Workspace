import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
 
User = settings.AUTH_USER_MODEL
 
 
# ------------------------------------------------------------------ #
# Workspace                                                           #
# ------------------------------------------------------------------ #
 
class Workspace(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=255)
    slug        = models.SlugField(max_length=255, unique=True, null=True, blank=True)
    description = models.TextField(blank=True, default="")
    avatar_url  = models.URLField(null=True, blank=True)
    owner       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_workspaces")
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
 
    class Meta:
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["created_at"]),
        ]
 
    def __str__(self):
        return self.name
 
 
class Membership(models.Model):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
        ("guest", "Guest"),
    ]
 
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    workspace  = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="members")
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    joined_at  = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        unique_together = ("user", "workspace")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["workspace"]),
            models.Index(fields=["workspace", "role"]),   # RBAC queries
        ]
 
    def __str__(self):
        return f"{self.user} in {self.workspace} ({self.role})"
 
 
class Invitation(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("expired",  "Expired"),
    ]
 
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace   = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email       = models.EmailField(db_index=True)
    role        = models.CharField(max_length=10, choices=Membership.ROLE_CHOICES, default="member")
    invited_by  = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invitations")
    # CharField token avoids UUID hyphen URL-routing issues
    token       = models.CharField(max_length=64, unique=True, db_index=True,
                                   default=lambda: uuid.uuid4().hex)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at  = models.DateTimeField(auto_now_add=True)
    expires_at  = models.DateTimeField()
 
    def is_valid(self):
        return self.status == "pending" and self.expires_at > timezone.now()
 
 
class WorkspaceInviteLink(models.Model):
    """Public shareable invite link (no email required)."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace  = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invite_links")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    token      = models.CharField(max_length=64, unique=True, db_index=True,
                                  default=lambda: uuid.uuid4().hex)
    role       = models.CharField(max_length=10, choices=Membership.ROLE_CHOICES, default="member")
    max_uses   = models.PositiveIntegerField(null=True, blank=True)
    use_count  = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
 
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_uses and self.use_count >= self.max_uses:
            return False
        return True
 
 
# ------------------------------------------------------------------ #
# Teams                                                               #
# ------------------------------------------------------------------ #
 
class Team(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace   = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="teams")
    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_teams")
    created_at  = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        unique_together = ("workspace", "name")
 
    def __str__(self):
        return self.name
 
 
class TeamMembership(models.Model):
    ROLE_CHOICES = [("lead", "Lead"), ("member", "Member")]
 
    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="team_memberships")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
 
    class Meta:
        unique_together = ("user", "team")
        indexes = [models.Index(fields=["team"])]
 
 
# ------------------------------------------------------------------ #
# Channels (Slack-like)                                               #
# ------------------------------------------------------------------ #
 
class Channel(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace   = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="channels")
    name        = models.CharField(max_length=255)
    topic       = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_private  = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_channels")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
 
    class Meta:
        unique_together = ("workspace", "name")
        indexes = [
            models.Index(fields=["workspace"]),
            models.Index(fields=["workspace", "is_private"]),
        ]
 
    def __str__(self):
        return f"#{self.name}"
 
 
class ChannelMembership(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="channel_memberships")
    channel    = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="memberships")
    joined_at  = models.DateTimeField(auto_now_add=True)
    # Last time the user read this channel — for unread counts
    last_read  = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        unique_together = ("user", "channel")
        indexes = [models.Index(fields=["channel"]), models.Index(fields=["user"])]
 
 
# ------------------------------------------------------------------ #
# Messages                                                            #
# ------------------------------------------------------------------ #
 
class Message(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel    = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="messages")
    workspace  = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="messages")
    sender     = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workspace_messages")
    # Thread support: parent=None means top-level message
    parent     = models.ForeignKey("self", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="replies")
    content    = models.TextField()
    is_edited  = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["channel", "created_at"]),   # critical for pagination
            models.Index(fields=["workspace"]),
            models.Index(fields=["sender"]),
        ]
 
 
class MessageReaction(models.Model):
    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reactions")
    user    = models.ForeignKey(User, on_delete=models.CASCADE)
    emoji   = models.CharField(max_length=20)
 
    class Meta:
        unique_together = ("message", "user", "emoji")
 
 
class PinnedMessage(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel   = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="pins")
    message   = models.ForeignKey(Message, on_delete=models.CASCADE)
    pinned_by = models.ForeignKey(User, on_delete=models.CASCADE)
    pinned_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        unique_together = ("channel", "message")
 
 
# ------------------------------------------------------------------ #
# Notifications (workspace-scoped)                                    #
# ------------------------------------------------------------------ #
 
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("invite",    "Invite"),
        ("mention",   "Mention"),
        ("message",   "Message"),
        ("role",      "Role Change"),
        ("system",    "System"),
    ]
 
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workspace_notifications")
    workspace  = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="notifications")
    type       = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default="system")
    message    = models.TextField()
    metadata   = models.JSONField(null=True, blank=True)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["workspace"]),
        ]
 