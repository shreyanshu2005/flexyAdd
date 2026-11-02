from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import ValidationError


class UserService:
    @staticmethod
    def model():
        return get_user_model()

    @classmethod
    @transaction.atomic
    def create_user(cls, data):
        user_model = cls.model()
        if user_model.objects.filter(email__iexact=data["email"]).exists():
            raise ValidationError({"email": "A user with this email already exists."})
        user = user_model.objects.create_user(
            email=data["email"],
            password=data["password"],
            role=data.get("role", "VIEWER"),
            **({"workspace": data["workspace"]} if data.get("workspace") else {}),
        )
        return user

    @classmethod
    @transaction.atomic
    def register(cls, data):
        """Self-service signup: creates a brand-new workspace with its first admin."""
        from users.models import Workspace

        if cls.model().objects.filter(email__iexact=data["email"]).exists():
            raise ValidationError({"email": "A user with this email already exists."})
        workspace = Workspace.objects.create(name=data["workspace_name"].strip())
        return cls.model().objects.create_user(
            email=data["email"], password=data["password"], role="ADMIN", workspace=workspace
        )

    @classmethod
    @transaction.atomic
    def assign_role(cls, user, role):
        if user.role == role:
            return user
        user.role = role
        user.full_clean(exclude=["password"])
        user.save(update_fields=["role"])
        return user

    @classmethod
    @transaction.atomic
    def set_status(cls, user, is_active):
        if user.is_active == is_active:
            return user
        user.is_active = is_active
        user.save(update_fields=["is_active"])
        return user
