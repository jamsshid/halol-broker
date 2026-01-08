from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
import logging

from ..serializers import (
    UserDetailSerializer,
    RegisterSerializer,
    LoginSerializer,
    GoogleAuthSerializer,
    ChangePasswordSerializer,
)
from ..models import Account, Wallet

User = get_user_model()
logger = logging.getLogger(__name__)


def get_tokens_for_user(user):
    """Generate JWT tokens for user"""
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    """
    Register new user

    POST /api/auth/register/
    {
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "password1": "StrongPass123!",
        "password2": "StrongPass123!"
    }
    """
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save(request)

        # Create demo account automatically
        account_number = f"D{user.id:08d}"
        account = Account.objects.create(
            user=user,
            account_number=account_number,
            account_type="demo",
            balance=10000.00,
            status="active",
        )
        Wallet.objects.create(account=account)

        # Generate tokens
        tokens = get_tokens_for_user(user)

        return Response(
            {
                "message": "Registration successful",
                "user": UserDetailSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login with email and password

    POST /api/auth/login/
    {
        "email": "user@example.com",
        "password": "password123"
    }
    """
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data["email"].lower()
    password = serializer.validated_data["password"]

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response(
            {"error": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.check_password(password):
        return Response(
            {"error": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        return Response(
            {"error": "Account is disabled"}, status=status.HTTP_403_FORBIDDEN
        )

    # Update last login
    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at"])

    # Generate tokens
    tokens = get_tokens_for_user(user)

    return Response(
        {
            "message": "Login successful",
            "user": UserDetailSerializer(user).data,
            "tokens": tokens,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def google_auth_view(request):
    """
    Google OAuth login/register

    POST /api/auth/google/
    {
        "access_token": "google_access_token_here"
    }
    """
    serializer = GoogleAuthSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    token = serializer.validated_data["access_token"]

    try:
        # Verify Google token
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"],
        )

        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Wrong issuer")

        google_id = idinfo["sub"]
        email = idinfo.get("email")
        first_name = idinfo.get("given_name", "")
        last_name = idinfo.get("family_name", "")
        avatar = idinfo.get("picture", "")

        # Check if user exists
        user = None
        try:
            user = User.objects.get(google_id=google_id)
        except User.DoesNotExist:
            try:
                # Check by email
                user = User.objects.get(email=email)
                user.google_id = google_id
                user.avatar = avatar
                user.save()
            except User.DoesNotExist:
                # Create new user
                user = User.objects.create_user(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    google_id=google_id,
                    avatar=avatar,
                    is_verified=True,  # Google verified
                )

                # Create demo account
                account_number = f"D{user.id:08d}"
                account = Account.objects.create(
                    user=user,
                    account_number=account_number,
                    account_type="demo",
                    balance=10000.00,
                    status="active",
                )
                Wallet.objects.create(account=account)

        # Update last login
        user.last_login_at = timezone.now()
        user.save(update_fields=["last_login_at"])

        # Generate tokens
        tokens = get_tokens_for_user(user)

        return Response(
            {
                "message": "Google authentication successful",
                "user": UserDetailSerializer(user).data,
                "tokens": tokens,
            }
        )

    except ValueError as e:
        logger.error(f"Google auth error: {str(e)}")
        return Response(
            {"error": "Invalid Google token"}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Logout user (blacklist refresh token)

    POST /api/auth/logout/
    {
        "refresh": "refresh_token_here"
    }
    """
    try:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST
            )

        token = RefreshToken(refresh_token)
        token.blacklist()

        return Response({"message": "Logout successful"})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_profile_view(request):
    """
    Get current user profile

    GET /api/auth/profile/
    """
    serializer = UserDetailSerializer(request.user)
    return Response(serializer.data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_profile_view(request):
    """
    Update user profile

    PATCH /api/auth/profile/
    {
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+998901234567"
    }
    """
    serializer = UserDetailSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "Profile updated successfully", "user": serializer.data}
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """
    Change password

    POST /api/auth/change-password/
    {
        "old_password": "oldpass123",
        "new_password1": "newpass123",
        "new_password2": "newpass123"
    }
    """
    serializer = ChangePasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = request.user

    # Check old password
    if not user.check_password(serializer.validated_data["old_password"]):
        return Response(
            {"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST
        )

    # Set new password
    user.set_password(serializer.validated_data["new_password1"])
    user.save()

    return Response({"message": "Password changed successfully"})
