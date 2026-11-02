from __future__ import annotations

from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.constants import ADMIN, ANALYST, EXPENSE, INCOME
from records.models import Record
from users.models import User


class RecordAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="StrongPass123")
        self.analyst = User.objects.create_user(email="analyst@example.com", password="StrongPass123", role=ANALYST)
        self.client.force_authenticate(self.admin)

    def test_admin_can_create_and_soft_delete_record(self):
        response = self.client.post(
            reverse("records-list"),
            {
                "amount": "1000.00",
                "type": INCOME,
                "category": "Salary",
                "date": "2026-01-01",
                "note": "monthly salary",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        record_id = response.data["data"]["id"]

        delete_response = self.client.delete(reverse("records-detail", args=[record_id]))
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertTrue(Record.all_objects.get(id=record_id).is_deleted)

    def test_analyst_can_view_but_not_create(self):
        self.client.force_authenticate(self.analyst)
        list_response = self.client.get(reverse("records-list"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        create_response = self.client.post(
            reverse("records-list"),
            {
                "amount": "50.00",
                "type": EXPENSE,
                "category": "Coffee",
                "date": "2026-01-01",
                "note": "client meeting",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filter_by_category_and_date(self):
        Record.objects.create(user=self.admin, amount=200, type=INCOME, category="Salary", date=date(2026, 1, 1), note="jan")
        Record.objects.create(user=self.admin, amount=50, type=EXPENSE, category="Food", date=date(2026, 1, 2), note="lunch")
        response = self.client.get(reverse("records-list"), {"category": "Salary", "start_date": "2026-01-01", "end_date": "2026-01-31"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 1)


class RecordCsvTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="StrongPass123")
        self.analyst = User.objects.create_user(email="analyst@example.com", password="StrongPass123", role=ANALYST)
        self.viewer = User.objects.create_user(email="viewer@example.com", password="StrongPass123")
        Record.objects.create(user=self.admin, amount="10.00", type=INCOME, category="=SUM(A1)", date=date(2026, 1, 5), note="hi")

    def test_export_escapes_formulas_and_respects_roles(self):
        self.client.force_authenticate(self.analyst)
        res = self.client.get("/api/records/export/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("'=SUM(A1)", res.content.decode())
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get("/api/records/export/").status_code, 403)

    def test_import_is_admin_only_and_all_or_nothing(self):
        good = "date,type,category,amount,note\n2026-02-01,income,Salary,500,Feb\n2026-02-02,expense,Rent,200,\n"
        bad = good + "2026-02-03,bogus,Food,-5,x\n"
        self.client.force_authenticate(self.analyst)
        self.assertEqual(self.client.post("/api/records/import/", {"csv": good}, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post("/api/records/import/", {"csv": bad}, format="json").status_code, 400)
        self.assertEqual(Record.objects.count(), 1)
        res = self.client.post("/api/records/import/", {"csv": good}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Record.objects.count(), 3)


class WorkspaceAndSmartFeatureTests(APITestCase):
    def register(self, name, email):
        res = self.client.post("/api/users/register/", {"workspace_name": name, "email": email, "password": "StrongPass123"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        return User.objects.get(email=email)

    def test_workspaces_are_isolated(self):
        a, b = self.register("Acme", "a@acme.com"), self.register("Beta", "b@beta.com")
        self.client.force_authenticate(a)
        self.client.post("/api/records/", {"amount": "100", "type": "income", "category": "Salary", "date": "2026-01-01"}, format="json")
        self.client.post("/api/budgets/", {"category": "Food", "monthly_limit": "50"}, format="json")
        self.client.force_authenticate(b)
        self.assertEqual(self.client.get("/api/records/").json()["data"]["count"], 0)
        self.assertEqual(self.client.get("/api/dashboard/summary/").json()["data"]["summary"]["transaction_count"], 0)
        self.assertEqual(self.client.get("/api/budgets/").json()["data"], [])
        self.assertEqual(self.client.get("/api/users/").json()["data"]["count"], 1)
        self.assertEqual(self.client.get("/api/records/export/").content.decode().count("\n"), 1)  # header only
        rid = Record.objects.get(workspace=a.workspace).id
        self.assertEqual(self.client.get(f"/api/records/{rid}/").status_code, 404)

    def test_category_normalised_and_budget_alerts(self):
        admin = self.register("Acme", "a@acme.com")
        self.client.force_authenticate(admin)
        for cat in ("Food", "food ", "FOOD"):
            self.client.post("/api/records/", {"amount": "60", "type": "expense", "category": cat, "date": date.today().isoformat()}, format="json")
        self.assertEqual(set(Record.objects.values_list("category", flat=True)), {"Food"})
        self.client.post("/api/budgets/", {"category": "food", "monthly_limit": "100"}, format="json")
        data = self.client.get("/api/budgets/status/").json()["data"]
        self.assertEqual(data["budgets"][0]["state"], "over")
        self.assertTrue(data["alerts"])

    def test_quick_add_learns_from_history(self):
        admin = self.register("Acme", "a@acme.com")
        self.client.force_authenticate(admin)
        Record.objects.create(user=admin, amount="90", type=EXPENSE, category="Pet Care", date=date(2026, 1, 2), note="vet visit for bruno")
        res = self.client.post("/api/records/parse/", {"text": "paid Rs 1,250 for bruno vet yesterday"}, format="json").json()["data"]
        self.assertEqual((res["amount"], res["type"], res["category"], res["source"]), ("1250.00", "expense", "Pet Care", "learned"))
        self.assertEqual(res["date"], (date.today() - __import__("datetime").timedelta(days=1)).isoformat())
        res = self.client.post("/api/records/parse/", {"text": "got 85k salary on 1 oct"}, format="json").json()["data"]
        self.assertEqual((res["amount"], res["type"], res["category"]), ("85000.00", "income", "Salary"))
        self.assertEqual(self.client.post("/api/records/parse/", {"text": "bought lunch"}, format="json").status_code, 400)
