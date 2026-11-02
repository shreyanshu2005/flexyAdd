from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.constants import ADMIN, ANALYST, VIEWER
from users.models import User


class UserAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="StrongPass123")
        self.viewer = User.objects.create_user(email="viewer@example.com", password="StrongPass123", role=VIEWER)
        self.client.force_authenticate(self.admin)

    def test_admin_can_create_user(self):
        response = self.client.post(
            reverse("users-list"),
            {"email": "analyst@example.com", "password": "StrongPass123", "role": ANALYST},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["role"], ANALYST)

    def test_admin_can_assign_role(self):
        response = self.client.patch(
            reverse("users-assign-role", args=[self.viewer.id]),
            {"role": ANALYST},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.viewer.refresh_from_db()
        self.assertEqual(self.viewer.role, ANALYST)

    def test_non_admin_is_blocked(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get(reverse("users-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SetupAdminCommandTests(APITestCase):
    def test_creates_admin_then_blocks_second_run(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        call_command("setup_admin", "--email", "a@example.com", "--password", "Password123")
        self.assertEqual(User.objects.get(email="a@example.com").role, "ADMIN")
        with self.assertRaises(CommandError):
            call_command("setup_admin", "--email", "b@example.com", "--password", "Password123")
        call_command("setup_admin", "--email", "b@example.com", "--password", "Password123", "--skip-if-exists")
        self.assertFalse(User.objects.filter(email="b@example.com").exists())


class LoginCaseInsensitiveTests(APITestCase):
    def test_register_then_login_works_with_any_email_capitalisation(self):
        res = self.client.post("/api/users/register/", {"workspace_name": "W", "email": "Me@Gmail.com", "password": "StrongPass123"}, format="json")
        self.assertEqual(res.status_code, 201)
        for email in ("Me@Gmail.com", "me@gmail.com", " ME@GMAIL.COM "):
            login = self.client.post("/api/auth/login/", {"email": email, "password": "StrongPass123"}, format="json")
            self.assertEqual(login.status_code, 200, email)
