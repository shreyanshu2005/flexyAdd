from rest_framework.permissions import BasePermission

from core.constants import ADMIN, ANALYST, VIEWER


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.role == ADMIN)


class IsAnalystOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.role in {ANALYST, ADMIN}
        )


class IsViewerOrAbove(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.role in {VIEWER, ANALYST, ADMIN})
