import hashlib
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import UntypedToken
from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
from .models import User, UserSession, SecurityEvent
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache



def generate_device_id(request):
    raw = (
        request.META.get("HTTP_USER_AGENT", "") +
        request.META.get("REMOTE_ADDR", "")
    )
    return hashlib.sha256(raw.encode()).hexdigest()


@api_view(["GET"])
def validate_token(request):
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return Response(status=401)

    token = auth_header.split(" ")[1]

    cached = cache.get(f"session:{token}")

    if cached:
        response = Response(status=200)
        response["X-User-ID"] = str(cached["user_id"])
        response["X-User-Email"] = cached["email"]
        
        # Add current workspace if set
        workspace_id = cache.get(f"current_workspace:{cached['user_id']}")
        if workspace_id:
            response["X-Workspace-ID"] = workspace_id
        
        return response

    try:
        UntypedToken(token)
        return Response(status=200)
    except:
        return Response(status=401)
    

@api_view(["POST"])
def refresh_view(request):
    refresh_token = request.data.get("refresh")

    if not refresh_token:
        return Response({"error": "Refresh token required"}, status=400)

    try:
        token = RefreshToken(refresh_token)

        user_id = token["user_id"]

        session = UserSession.objects.filter(
            user_id=user_id,
            refresh_token=refresh_token
        ).first()

        if not session or session.is_expired():
            return Response({"error": "Invalid session"}, status=401)

        new_refresh = RefreshToken.for_user(session.user)

        cache.delete(f"session:{refresh_token}")

        session.refresh_token = str(new_refresh)
        session.expires_at = timezone.now() + timedelta(days=7)
        session.save()

        cache.set(f"session:{str(new_refresh)}", {
            "user_id": session.user.id,
            "email": session.user.email
        }, timeout=60 * 60 * 24 * 7)

        return Response({
            "access": str(new_refresh.access_token),
            "refresh": str(new_refresh)
        })

    except Exception:
        return Response({"error": "Invalid token"}, status=401)
    

@api_view(["POST"])
def login_view(request):
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password:
        return Response({"error": "Email and password required"}, status=400)

    user = authenticate(request, username=email, password=password)

    if user is None:
        return Response({"error": "Invalid credentials"}, status=401)

    device_id = generate_device_id(request)
    new_device = not UserSession.objects.filter(user=user, device_info=device_id).exists()
    existing_sessions = UserSession.objects.filter(user=user)

    if new_device:
        SecurityEvent.objects.create(
            user=user,
            event_type="new_device_login",
            ip_address=request.META.get("REMOTE_ADDR", "")
        )

    for session in existing_sessions:
        if session.ip_address and session.ip_address != request.META.get("REMOTE_ADDR"):
            SecurityEvent.objects.create(
                user=user,
                event_type="suspicious_login",
                ip_address=request.META.get("REMOTE_ADDR", "")
            )
            break

    refresh = RefreshToken.for_user(user)

    UserSession.objects.create(
        user=user,
        refresh_token=str(refresh),
        device_info=device_id,
        ip_address=request.META.get("REMOTE_ADDR"),
        expires_at=timezone.now() + timedelta(days=7)
    )

    cache_key = f"session:{str(refresh)}"
    cache.set(cache_key, {
        "user_id": user.id,
        "email": user.email
    }, timeout=60 * 60 * 24 * 7)

    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "id": user.id,
            "email": user.email
        }
    })


@api_view(["POST"])
def register_view(request):
    username = request.data.get("username")
    email = request.data.get("email")
    full_name = request.data.get("full_name")
    password = request.data.get("password")

    if not username or not email or not full_name or not password:
        return Response({"error": "All fields required"}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already taken"}, status=400)

    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already exists"}, status=400)

    user = User.objects.create_user(
        username=username,
        email=email,
        full_name=full_name,
        password=password
    )

    return Response({
        "message": "User created successfully",
        "user_id": user.id
    }, status=201)


@api_view(["POST"])
def logout_view(request):
    refresh_token = request.data.get("refresh")

    if not refresh_token:
        return Response({"error": "Refresh token required"}, status=400)

    session = UserSession.objects.filter(refresh_token=refresh_token).first()

    if session:
        session.delete()

    cache.delete(f"session:{refresh_token}")

    return Response({"message": "Logged out"})


@api_view(["POST"])
def logout_all_view(request):
    user_id = request.data.get("user_id")

    UserSession.objects.filter(user_id=user_id).delete()

    return Response({"message": "Logged out from all devices"})