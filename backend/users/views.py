from __future__ import annotations

import logging
import os

from django.core.cache import cache
from django.db import DatabaseError, OperationalError, ProgrammingError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.permissions import IsAdminRole
from users.services import UserService
from core.responses import success_response
from users.models import User
from users.serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    UserCreateSerializer,
    UserRoleUpdateSerializer,
    UserStatusUpdateSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema(tags=["Auth"], summary="Login")
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_scope = "auth"


@extend_schema(tags=["Auth"], summary="Refresh access token")
class CustomTokenRefreshView(TokenRefreshView):
    throttle_scope = "auth"


@extend_schema_view(
    create=extend_schema(tags=["Users"], summary="Create user"),
    list=extend_schema(tags=["Users"], summary="List users"),
    retrieve=extend_schema(tags=["Users"], summary="Get user"),
    setup=extend_schema(tags=["Users"], summary="Initial admin setup"),
    assign_role=extend_schema(tags=["Users"], summary="Assign user role"),
    set_status=extend_schema(tags=["Users"], summary="Set user active status"),
)
class UserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.all().order_by("-created_at")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    throttle_scope = "users"

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action == "assign_role":
            return UserRoleUpdateSerializer
        if self.action == "set_status":
            return UserStatusUpdateSerializer
        return UserSerializer

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], url_path="setup")
    def setup(self, request, *args, **kwargs):
        """First-time setup: creates initial admin account with security checks"""

        # 1. CHECK: DB must be ready and empty
        try:
            if User.objects.exists():
                logger.warning(f"Setup attempted when DB not empty from {request.META.get('REMOTE_ADDR')}")
                raise ValidationError({"detail": "Database already initialized"})
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            logger.exception("Setup failed during database readiness check: %s", exc)
            raise APIException(
                "Database not ready. Run migrations and verify database environment variables."
            )

        # 2. CHECK: Rate limit - max 5 attempts per hour per IP
        client_ip = request.META.get("REMOTE_ADDR", "unknown")
        cache_key = f"setup_attempts:{client_ip}"
        attempts = cache.get(cache_key, 0)

        if attempts >= 5:
            logger.warning(f"Setup rate limit exceeded for {client_ip}")
            raise PermissionDenied("Too many setup attempts. Try again later.")

        # 3. CHECK: Require setup token
        setup_token = os.getenv("SETUP_TOKEN")
        if not setup_token:
            logger.error("SETUP_TOKEN not configured in environment")
            raise PermissionDenied("Setup not enabled")

        provided_token = request.data.get("setup_token")
        if provided_token != setup_token:
            cache.set(cache_key, attempts + 1, 3600)  # 1 hour
            logger.warning(f"Invalid setup token attempt from {client_ip}")
            raise PermissionDenied("Invalid setup token")

        # 4. CREATE: Admin user
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save(role="ADMIN", is_staff=True)
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            logger.exception("Setup failed while creating initial admin: %s", exc)
            raise APIException(
                "Unable to create initial admin. Run migrations and verify database connectivity."
            )

        logger.info(f"Setup complete: Admin {user.email} created from {client_ip}")
        cache.delete(cache_key)  # Clear attempts on success

        return success_response(UserSerializer(user).data, status_code=status.HTTP_201_CREATED)

    def get_queryset(self):
        return User.objects.filter(workspace_id=self.request.user.workspace_id).order_by("-created_at")

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], url_path="register")
    def register(self, request):
        """Create a new workspace and its first admin (disable with ALLOW_REGISTRATION=0)."""
        if os.getenv("ALLOW_REGISTRATION", "1") != "1":
            raise PermissionDenied("Registration is disabled.")
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.register(serializer.validated_data)
        return success_response(UserSerializer(user).data, status_code=status.HTTP_201_CREATED)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return success_response(UserSerializer(user).data, status_code=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        users = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(users)
        if page is not None:
            serializer = UserSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = UserSerializer(users, many=True)
        return success_response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        return success_response(UserSerializer(user).data)

    @action(detail=True, methods=["patch"], url_path="role")
    def assign_role(self, request, pk=None):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()
        return success_response(UserSerializer(updated_user).data)

    @action(detail=True, methods=["patch"], url_path="status")
    def set_status(self, request, pk=None):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()
        return success_response(UserSerializer(updated_user).data)
