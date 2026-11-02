from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from datetime import date

from core.constants import ANALYST, EXPENSE, INCOME, VIEWER
from records.models import Record
from users.models import User


class DashboardAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="StrongPass123")
        self.analyst = User.objects.create_user(email="analyst@example.com", password="StrongPass123", role=ANALYST)
        self.viewer = User.objects.create_user(email="viewer@example.com", password="StrongPass123", role=VIEWER)
        # Current period
        Record.objects.create(user=self.admin, amount=1000, type=INCOME, category="Salary", date=date(2026, 1, 1), note="salary")
        Record.objects.create(user=self.admin, amount=250, type=EXPENSE, category="Food", date=date(2026, 1, 2), note="groceries")
        Record.objects.create(user=self.admin, amount=150, type=EXPENSE, category="Rent", date=date(2026, 1, 3), note="house rent")
        Record.objects.create(user=self.analyst, amount=200, type=INCOME, category="Consulting", date=date(2026, 1, 4), note="consulting work")
        # Previous period
        Record.objects.create(user=self.admin, amount=500, type=INCOME, category="Salary", date=date(2025, 12, 1), note="salary")
        Record.objects.create(user=self.admin, amount=100, type=EXPENSE, category="Food", date=date(2025, 12, 2), note="groceries")

    def test_viewer_can_read_dashboard_summary(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get(reverse("dashboard-summary"), {"start_date": "2026-01-01", "end_date": "2026-01-31"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["summary"]["transaction_count"], 4)
        self.assertEqual(response.data["data"]["summary"]["total_income"], 1200)
        self.assertEqual(response.data["data"]["summary"]["total_expense"], 400)
        self.assertEqual(response.data["data"]["period_comparison"]["current_period"]["total_income"], 1200)
        self.assertEqual(response.data["data"]["period_comparison"]["previous_period"]["total_income"], 500)
        self.assertEqual(response.data["data"]["top_spending_categories"][0]["category"], "Food")
        self.assertTrue(response.data["data"]["insights"])

    def test_date_filters_are_validated(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("dashboard-summary"), {"start_date": "2026-02-01", "end_date": "2026-01-01"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_receives_user_breakdown(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("dashboard-summary"), {"start_date": "2026-01-01", "end_date": "2026-01-31"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["user_breakdown"]), 2)
        self.assertEqual(response.data["data"]["user_breakdown"][0]["user_email"], "admin@example.com")

    def test_split_dashboard_endpoints_are_available(self):
        self.client.force_authenticate(self.viewer)

        comparison = self.client.get(reverse("dashboard-comparison"), {"start_date": "2026-01-01", "end_date": "2026-01-31"})
        categories = self.client.get(reverse("dashboard-categories"), {"start_date": "2026-01-01", "end_date": "2026-01-31"})
        top_spending = self.client.get(reverse("dashboard-top-spending"), {"start_date": "2026-01-01", "end_date": "2026-01-31"})
        trends = self.client.get(reverse("dashboard-trends"), {"start_date": "2026-01-01", "end_date": "2026-01-31"})
        insights = self.client.get(reverse("dashboard-insights"), {"start_date": "2026-01-01", "end_date": "2026-01-31"})

        self.assertEqual(comparison.status_code, status.HTTP_200_OK)
        self.assertIn("period_comparison", comparison.data["data"])

        self.assertEqual(categories.status_code, status.HTTP_200_OK)
        self.assertIn("category_breakdown", categories.data["data"])

        self.assertEqual(top_spending.status_code, status.HTTP_200_OK)
        self.assertIn("top_spending_categories", top_spending.data["data"])

        self.assertEqual(trends.status_code, status.HTTP_200_OK)
        self.assertIn("monthly_trends", trends.data["data"])

        self.assertEqual(insights.status_code, status.HTTP_200_OK)
        self.assertIn("insights", insights.data["data"])
