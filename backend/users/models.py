from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from core.constants import ROLE_CHOICES, VIEWER
from users.managers import UserManager


class Workspace(models.Model):
    """A tenant: every user, record and budget belongs to exactly one workspace."""

    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class User(AbstractBaseUser, PermissionsMixin):
    workspace = models.ForeignKey(Workspace, null=True, on_delete=models.PROTECT, related_name="members")
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=VIEWER, db_index=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        indexes = [models.Index(fields=["email"]), models.Index(fields=["role", "is_active"])]

    def __str__(self) -> str:
        return self.email
