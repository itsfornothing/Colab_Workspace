import hashlib
import logging
from datetime import timedelta
 
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings as django_settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
 
from .models import User, UserSession, SecurityEvent, TokenBlacklist, \
    PasswordResetToken, EmailVerification
 
logger = logging.getLogger(__name__)
 
FAILED_LOGIN_KEY    = "failed_logins:{email}"
FAILED_LOGIN_LIMIT  = 10
FAILED_LOGIN_WINDOW = 60 * 15   # 15 minutes lockout
 
 
def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")
 
 
def generate_device_id(request):
    raw = (
        request.META.get("HTTP_USER_AGENT", "") +
        get_client_ip(request)
    )
    return hashlib.sha256(raw.encode()).hexdigest()
 
 
def _blacklist_token(token_obj, user, reason=""):
    """Add a JWT's jti to the blacklist."""
    try:
        jti        = token_obj.get("jti", "")
        expires_at = timezone.now() + timedelta(
            seconds=token_obj.get("exp", 0) - token_obj.get("iat", 0)
        )
        if jti:
            TokenBlacklist.objects.get_or_create(
                jti=jti,
                defaults={"user": user, "expires_at": expires_at, "reason": reason},
            )
            cache.set(f"blacklist:{jti}", True, timeout=3600)
    except Exception:
        logger.exception("Failed to blacklist token")
 
 
def _is_token_blacklisted(jti: str) -> bool:
    """Fast Redis check first, DB fallback."""
    cached = cache.get(f"blacklist:{jti}")
    if cached is not None:
        return bool(cached)
    exists = TokenBlacklist.objects.filter(jti=jti).exists()
    cache.set(f"blacklist:{jti}", exists, timeout=3600)
    return exists
 
 
# ------------------------------------------------------------------ #
# Token validation (called by Nginx auth_request)                    #
# ------------------------------------------------------------------ #
 
@api_view(["GET"])
@permission_classes([AllowAny])
def validate_token(request):
    """
    Called by Nginx auth_request on every API request.
    Returns 200 with user headers on success, 401 on failure.
    Performance: Redis cache checked first — typical latency < 1ms.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return Response(status=401)
 
    token_str = auth_header.split(" ", 1)[1]
    cache_key = f"session:{token_str}"
    cached    = cache.get(cache_key)
 
    if cached:
        # Extend sliding session TTL on active use
        cache.expire(cache_key, django_settings.SESSION_CACHE_TTL)
 
        response = Response(status=200)
        response["X-User-ID"]    = str(cached["user_id"])
        response["X-User-Email"] = cached["email"]
        response["X-User-Role"]  = cached.get("role", "member")
 
        workspace_id = cache.get(f"current_workspace:{cached['user_id']}")
        if workspace_id:
            response["X-Workspace-ID"] = workspace_id
 
        return response
 
    try:
        token = UntypedToken(token_str)
        jti   = token.get("jti", "")
 
        # Zero Trust: check blacklist on every miss
        if jti and _is_token_blacklisted(jti):
            return Response(status=401)
 
        user_id = token.get("user_id")
        if not user_id:
            return Response(status=401)
 
        user = User.objects.get(id=user_id, is_active=True)
 
        payload = {"user_id": str(user.id), "email": user.email, "role": "member"}
        cache.set(cache_key, payload, timeout=django_settings.SESSION_CACHE_TTL)
 
        response = Response(status=200)
        response["X-User-ID"]    = str(user.id)
        response["X-User-Email"] = user.email
        response["X-User-Role"]  = "member"
        return response
 
    except (InvalidToken, TokenError):
        return Response(status=401)
    except User.DoesNotExist:
        return Response(status=401)
    except Exception:
        logger.exception("validate_token unexpected error")
        return Response(status=500)
 
 
# ------------------------------------------------------------------ #
# Register                                                            #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    username  = request.data.get("username", "").strip()
    email     = request.data.get("email", "").strip().lower()
    full_name = request.data.get("full_name", "").strip()
    password  = request.data.get("password", "")

    # Auto-generate username from email if not provided
    if not username and email:
        base = email.split("@")[0].replace(".", "_").replace("-", "_")
        username = base
        # Ensure uniqueness
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1

    if not all([username, email, full_name, password]):
        return Response({"error": "All fields required."}, status=400)
 
    if len(password) < 8:
        return Response({"error": "Password must be at least 8 characters."}, status=400)
 
    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already taken."}, status=400)
 
    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already registered."}, status=400)
 
    user = User.objects.create_user(
        username=username, email=email, full_name=full_name, password=password
    )
 
    # Send email verification
    _send_verification_email(user)
 
    SecurityEvent.objects.create(
        user=user, event_type="login",
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
 
    return Response({"message": "Account created. Please verify your email.", "user_id": str(user.id)}, status=201)
 
 
def _send_verification_email(user):
    from datetime import timedelta
    ev = EmailVerification.objects.create(
        user=user, expires_at=timezone.now() + timedelta(days=1)
    )
    # Link goes directly to the backend verify endpoint (works in browser)
    link = f"{django_settings.FRONTEND_URL}/api/auth/email/verify/?token={ev.token}"
    try:
        send_mail(
            "Verify your Collab Workspace email",
            f"Click the link below to verify your email address:\n\n{link}\n\nThis link expires in 24 hours.",
            django_settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
    except Exception:
        logger.exception("Failed to send verification email to %s", user.email)
 
 
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def verify_email(request):
    # Support both GET (browser link click) and POST (API call)
    token = request.query_params.get("token") or request.data.get("token")
    if not token:
        return Response({"error": "token required."}, status=400)
    try:
        ev = EmailVerification.objects.select_related("user").get(token=token)
    except EmailVerification.DoesNotExist:
        if request.method == "GET":
            from django.http import HttpResponse
            return HttpResponse("<html><body><h2>Invalid or expired verification link.</h2></body></html>", content_type="text/html")
        return Response({"error": "Invalid token."}, status=400)
    if ev.verified or ev.expires_at < timezone.now():
        if request.method == "GET":
            from django.http import HttpResponse
            return HttpResponse("<html><body><h2>This link has already been used or has expired.</h2></body></html>", content_type="text/html")
        return Response({"error": "Token expired or already used."}, status=400)
    ev.user.is_verified = True
    ev.user.save(update_fields=["is_verified"])
    ev.verified = True
    ev.save(update_fields=["verified"])
    if request.method == "GET":
        from django.http import HttpResponse
        return HttpResponse(
            "<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
            "<h2>✅ Email verified successfully!</h2>"
            "<p>You can now log in to the Collab Workspace app.</p>"
            "</body></html>",
            content_type="text/html"
        )
    return Response({"message": "Email verified."})
 
 
# ------------------------------------------------------------------ #
# Login                                                               #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    email    = request.data.get("email", "").strip().lower()
    password = request.data.get("password", "")
 
    if not email or not password:
        return Response({"error": "Email and password required."}, status=400)
 
    # Brute-force protection (gracefully skip if Redis unavailable)
    fail_key   = FAILED_LOGIN_KEY.format(email=email)
    try:
        fail_count = cache.get(fail_key, 0)
        if fail_count >= FAILED_LOGIN_LIMIT:
            return Response({"error": "Too many failed attempts. Try again in 15 minutes."}, status=429)
    except Exception:
        fail_count = 0  # Redis unavailable — skip rate limiting

    user = authenticate(request, username=email, password=password)

    if user is None:
        try:
            cache.set(fail_key, fail_count + 1, timeout=FAILED_LOGIN_WINDOW)
        except Exception:
            pass
        SecurityEvent.objects.create(
            user_id=User.objects.filter(email=email).values_list("id", flat=True).first(),
            event_type="failed_login",
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        ) if User.objects.filter(email=email).exists() else None
        return Response({"error": "Invalid credentials."}, status=401)
 
    # Clear fail counter on success
    # Clear fail counter on success
    try:
        cache.delete(fail_key)
    except Exception:
        pass

    ip         = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    device_id  = generate_device_id(request)

    existing_session = UserSession.objects.filter(user=user, device_info=device_id).first()
    is_new_device    = existing_session is None

    if is_new_device:
        SecurityEvent.objects.create(
            user=user, event_type="new_device_login",
            ip_address=ip, user_agent=user_agent,
        )
    else:
        if existing_session.ip_address and existing_session.ip_address != ip:
            SecurityEvent.objects.create(
                user=user, event_type="suspicious_login",
                ip_address=ip, user_agent=user_agent,
                metadata={"previous_ip": existing_session.ip_address},
            )

    refresh = RefreshToken.for_user(user)
    refresh["user_id"] = str(user.id)

    expires_at = timezone.now() + timedelta(days=7)

    UserSession.objects.update_or_create(
        user=user,
        device_info=device_id,
        defaults={
            "refresh_token": str(refresh),
            "ip_address":    ip,
            "user_agent":    user_agent,
            "expires_at":    expires_at,
            "last_used_at":  timezone.now(),
        },
    )

    try:
        cache.set(
            f"session:{str(refresh.access_token)}",
            {"user_id": str(user.id), "email": user.email},
            timeout=django_settings.SESSION_CACHE_TTL,
        )
    except Exception:
        pass  # Redis unavailable — session still works via DB

    SecurityEvent.objects.create(
        user=user, event_type="login", ip_address=ip, user_agent=user_agent
    )

    return Response({
        "access":  str(refresh.access_token),
        "refresh": str(refresh),
        "user":    {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
        },
    })
 
 
# ------------------------------------------------------------------ #
# Token refresh (with rotation)                                       #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_view(request):
    refresh_token = request.data.get("refresh")
    if not refresh_token:
        return Response({"error": "Refresh token required."}, status=400)
 
    try:
        old_token = RefreshToken(refresh_token)
        user_id   = old_token.get("user_id") or old_token.get("user_id")
    except (InvalidToken, TokenError):
        return Response({"error": "Invalid token."}, status=401)
 
    session = UserSession.objects.select_related("user").filter(
        refresh_token=refresh_token
    ).first()
 
    if not session or session.is_expired():
        return Response({"error": "Session expired or invalid."}, status=401)
 
    # Sliding session: extend expiry on use
    session.expires_at   = timezone.now() + timedelta(days=7)
    session.last_used_at = timezone.now()
 
    new_refresh = RefreshToken.for_user(session.user)
    new_refresh["user_id"] = str(session.user.id)
 
    # BUG FIX: revoke old access token by blacklisting its jti
    try:
        old_access = old_token.access_token
        _blacklist_token(old_access, session.user, reason="token_rotation")
    except Exception:
        pass
 
    cache.delete(f"session:{refresh_token}")
 
    session.refresh_token = str(new_refresh)
    session.save(update_fields=["refresh_token", "expires_at", "last_used_at"])
 
    cache.set(
        f"session:{str(new_refresh.access_token)}",
        {"user_id": str(session.user.id), "email": session.user.email},
        timeout=django_settings.SESSION_CACHE_TTL,
    )
 
    return Response({
        "access":  str(new_refresh.access_token),
        "refresh": str(new_refresh),
    })
 
 
# ------------------------------------------------------------------ #
# Logout                                                              #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    refresh_token = request.data.get("refresh")
    if not refresh_token:
        return Response({"error": "Refresh token required."}, status=400)
 
    session = UserSession.objects.select_related("user").filter(
        refresh_token=refresh_token
    ).first()
 
    if session:
        # Blacklist the current access token if provided
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            access_str = auth.split(" ", 1)[1]
            cache.delete(f"session:{access_str}")
            try:
                access = UntypedToken(access_str)
                _blacklist_token(access, session.user, reason="logout")
            except Exception:
                pass
 
        SecurityEvent.objects.create(
            user=session.user, event_type="logout",
            ip_address=get_client_ip(request),
        )
        session.delete()
 
    cache.delete(f"session:{refresh_token}")
    return Response({"message": "Logged out."})
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_all_view(request):
    """
    BUG FIX: Original accepted user_id from body with no auth — anyone
    could log out any user. Now uses request.user (requires IsAuthenticated).
    """
    sessions = UserSession.objects.filter(user=request.user)
    for session in sessions:
        cache.delete(f"session:{session.refresh_token}")
    sessions.delete()
 
    SecurityEvent.objects.create(
        user=request.user, event_type="logout",
        ip_address=get_client_ip(request),
        metadata={"scope": "all_devices"},
    )
    return Response({"message": "Logged out from all devices."})
 
 
# ------------------------------------------------------------------ #
# Token revocation (Zero Trust)                                       #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_token(request):
    """Immediately revoke a specific access token (add to blacklist)."""
    token_str = request.data.get("token") or request.headers.get("Authorization", "").split(" ", 1)[-1]
    if not token_str:
        return Response({"error": "token required."}, status=400)
    try:
        token = UntypedToken(token_str)
        _blacklist_token(token, request.user, reason="manual_revocation")
        cache.delete(f"session:{token_str}")
        SecurityEvent.objects.create(
            user=request.user, event_type="token_revoked",
            ip_address=get_client_ip(request),
        )
        return Response({"message": "Token revoked."})
    except Exception:
        return Response({"error": "Invalid token."}, status=400)
 
 
# ------------------------------------------------------------------ #
# Session management                                                  #
# ------------------------------------------------------------------ #
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_sessions(request):
    """Return all active sessions for the current user."""
    sessions = UserSession.objects.filter(user=request.user, expires_at__gt=timezone.now())
    return Response([
        {
            "id":           str(s.id),
            "device_info":  s.device_info,
            "ip_address":   s.ip_address,
            "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
            "expires_at":   s.expires_at.isoformat(),
            "created_at":   s.created_at.isoformat(),
        }
        for s in sessions
    ])
 
 
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_session(request, session_id):
    """Revoke a specific session by ID."""
    try:
        session = UserSession.objects.get(id=session_id, user=request.user)
        cache.delete(f"session:{session.refresh_token}")
        session.delete()
        return Response({"message": "Session removed."})
    except UserSession.DoesNotExist:
        return Response({"error": "Session not found."}, status=404)
 
 
# ------------------------------------------------------------------ #
# Password reset                                                      #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    email = request.data.get("email", "").strip().lower()
    if not email:
        return Response({"error": "email required."}, status=400)
 
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Don't reveal whether email exists
        return Response({"message": "If that email is registered, a reset link has been sent."})
 
    token = PasswordResetToken.objects.create(
        user=user,
        expires_at=timezone.now() + timedelta(hours=2),
    )
    link = f"{django_settings.FRONTEND_URL}/reset-password/{token.token}"
    try:
        send_mail("Password Reset", f"Reset here: {link}",
                  django_settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception:
        logger.exception("Failed to send password reset email")
 
    return Response({"message": "If that email is registered, a reset link has been sent."})
 
 
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    token_str   = request.data.get("token")
    new_password = request.data.get("password", "")
 
    if not token_str or not new_password:
        return Response({"error": "token and password required."}, status=400)
    if len(new_password) < 8:
        return Response({"error": "Password must be at least 8 characters."}, status=400)
 
    try:
        prt = PasswordResetToken.objects.select_related("user").get(token=token_str)
    except PasswordResetToken.DoesNotExist:
        return Response({"error": "Invalid or expired token."}, status=400)
 
    if not prt.is_valid():
        return Response({"error": "Token expired or already used."}, status=400)
 
    prt.user.set_password(new_password)
    prt.user.save(update_fields=["password"])
    prt.used = True
    prt.save(update_fields=["used"])
 
    # Invalidate all sessions after password change
    UserSession.objects.filter(user=prt.user).delete()
    SecurityEvent.objects.create(user=prt.user, event_type="password_change")
 
    return Response({"message": "Password updated."})


# ------------------------------------------------------------------ #
# Profile (GET / PATCH)                                               #
# ------------------------------------------------------------------ #

@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def profile_view(request):
    user = request.user
    if request.method == "GET":
        return Response({
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "full_name": getattr(user, "full_name", ""),
            "job_title": getattr(user, "job_title", "") or "",
            "bio": getattr(user, "bio", "") or "",
            "avatar_url": getattr(user, "avatar_url", None),
            "notification_in_app": getattr(user, "notification_in_app", True),
            "notification_email": getattr(user, "notification_email", False),
        })

    # PATCH — use raw SQL UPDATE so it works even if migrations haven't run yet
    from django.db import connection

    allowed_fields = ("full_name", "job_title", "bio", "avatar_url")
    updates = {f: request.data[f] for f in allowed_fields if f in request.data}

    if not updates:
        return Response({"message": "Nothing to update."})

    # Try ORM first (works when migration has been applied)
    try:
        for field, value in updates.items():
            setattr(user, field, value)
        user.save(update_fields=list(updates.keys()))
        return Response({"message": "Profile updated."})
    except Exception as orm_err:
        logger.warning("ORM save failed (%s), falling back to raw SQL", orm_err)

    # Fallback: raw SQL UPDATE for each field individually
    # This handles the case where the column exists in DB but ORM cache is stale,
    # or where the migration was applied manually outside Django.
    saved = []
    update_sql = {
        "full_name": 'UPDATE app_user SET "full_name" = %s WHERE id = %s',
        "job_title": 'UPDATE app_user SET "job_title" = %s WHERE id = %s',
        "bio": 'UPDATE app_user SET "bio" = %s WHERE id = %s',
        "avatar_url": 'UPDATE app_user SET "avatar_url" = %s WHERE id = %s',
    }
    with connection.cursor() as cursor:
        for field, value in updates.items():
            sql = update_sql.get(field)
            if sql is None:
                continue
            try:
                cursor.execute(sql, [value, str(user.id)])
                saved.append(field)
            except Exception as sql_err:
                logger.warning("Raw SQL update failed for field %s: %s", field, sql_err)

    if saved:
        return Response({"message": "Profile updated."})

    # Nothing could be saved — migration definitely not applied
    return Response(
        {"error": "Profile fields not available. Please run: python manage.py migrate"},
        status=500,
    )


# ------------------------------------------------------------------ #
# Change Password                                                     #
# ------------------------------------------------------------------ #

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    current_password = request.data.get("current_password", "")
    new_password = request.data.get("new_password", "")

    if not current_password or not new_password:
        return Response({"error": "current_password and new_password are required."}, status=400)

    if len(new_password) < 8:
        return Response({"error": "New password must be at least 8 characters."}, status=400)

    if not request.user.check_password(current_password):
        return Response({"error": "Current password is incorrect."}, status=400)

    request.user.set_password(new_password)
    request.user.save(update_fields=["password"])

    # Invalidate all other sessions after password change
    UserSession.objects.filter(user=request.user).exclude(
        refresh_token=request.data.get("refresh_token", "")
    ).delete()

    SecurityEvent.objects.create(
        user=request.user,
        event_type="password_change",
        ip_address=get_client_ip(request),
    )

    return Response({"message": "Password changed successfully."})


# ------------------------------------------------------------------ #
# Notification Preferences                                            #
# ------------------------------------------------------------------ #

@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def notification_preferences_view(request):
    user = request.user
    if request.method == "GET":
        return Response({
            "in_app": getattr(user, "notification_in_app", True),
            "email": getattr(user, "notification_email", False),
        })

    # PATCH — update preferences
    if "in_app" in request.data:
        val = request.data["in_app"]
        if isinstance(val, bool):
            try:
                user.notification_in_app = val
                user.save(update_fields=["notification_in_app"])
            except Exception:
                pass  # Field may not exist yet — ignore gracefully
    if "email" in request.data:
        val = request.data["email"]
        if isinstance(val, bool):
            try:
                user.notification_email = val
                user.save(update_fields=["notification_email"])
            except Exception:
                pass

    return Response({
        "in_app": getattr(user, "notification_in_app", True),
        "email": getattr(user, "notification_email", False),
    })
