from __future__ import annotations

from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from core.constants import ANALYST, EXPENSE, INCOME, LENT, NORMAL, REPAYMENT
from records.models import Record
from records.sms_parser import SmsIgnored, parse_upi_sms
from users.models import User

TODAY = date(2026, 11, 2)
HDFC_DEBIT = "Sent Rs.250.00\nFrom HDFC Bank A/c *1234\nTo RAHUL SHARMA\nOn 02/11/26\nRef 312345678901\nNot You? Call 18002586161/SMS BLOCK UPI to 7308080808"
VPA_DEBIT = "Rs. 250.00 debited from a/c **1234 on 02-11-26 to VPA rahul@okaxis (UPI Ref No {ref}). Not you? Call 18002586161"
VPA_CREDIT = "Credit Alert! Rs.{amt} credited to HDFC Bank A/c xx1234 on 02-11-26 from VPA rahul@okaxis (UPI Ref No {ref})"


class SmsParserTests(APITestCase):
    def check(self, sms, direction, amount, who, ref="312345678901"):
        p = parse_upi_sms(sms, TODAY)
        self.assertEqual((p.direction, p.amount, p.counterparty, p.ref), (direction, Decimal(amount), who, ref), sms)
        self.assertEqual(p.when, TODAY)

    def test_common_bank_formats(self):
        self.check(HDFC_DEBIT, "debit", "250.00", "Rahul Sharma")
        self.check(VPA_DEBIT.format(ref="312345678901"), "debit", "250.00", "rahul@okaxis")
        self.check(VPA_CREDIT.format(amt="500.00", ref="312345678901"), "credit", "500.00", "rahul@okaxis")
        self.check("Dear UPI user A/C X1234 debited by 250.0 on date 02Nov26 trf to RAHUL SHARMA Refno 312345678901. If not u? call 1800", "debit", "250.00", "Rahul Sharma")
        self.check("Dear UPI user A/C X1234 credited by Rs500 on date 02Nov26 trf from RAHUL SHARMA Refno 312345678901 -SBI", "credit", "500.00", "Rahul Sharma")
        self.check("ICICI Bank Acct XX123 debited for Rs 250.00 on 02-Nov-26; RAHUL SHARMA credited. UPI:312345678901. Call 18002662", "debit", "250.00", "Rahul Sharma")
        self.check("Dear Customer, Acct XX123 is credited with Rs 500.00 on 02-Nov-26 from RAHUL SHARMA. UPI:312345678901-ICICI Bank.", "credit", "500.00", "Rahul Sharma")
        self.check("INR 250.00 debited A/c no. XX1234 02-11-26, 14:30:00 UPI/P2A/312345678901/RAHUL SHARMA SMS BLOCK UPI to 1800", "debit", "250.00", "Rahul Sharma")
        self.check("INR 500.00 credited to A/c no. XX1234 02-11-26, 14:30:00 UPI/P2A/312345678901/RAHUL SHARMA -Axis Bank", "credit", "500.00", "Rahul Sharma")
        self.check("Sent Rs.1,250.50 from Kotak Bank AC X1234 to swiggy@okicici on 02-11-26.UPI Ref 312345678901. Avl Bal Rs 12,000.50", "debit", "1250.50", "swiggy@okicici")
        self.check("Received Rs.500.00 in your Kotak Bank AC X1234 from rahul@okaxis on 02-11-26.UPI Ref:312345678901", "credit", "500.00", "rahul@okaxis")

    def test_balance_is_never_mistaken_for_amount(self):
        p = parse_upi_sms("Avl Bal Rs 99,999.00. Sent Rs.40.00 from Kotak Bank AC X1234 to tea@ybl on 02-11-26.UPI Ref 312345678901", TODAY)
        self.assertEqual(p.amount, Decimal("40.00"))

    def test_non_payments_are_ignored(self):
        for sms in (
            "Your OTP for UPI txn is 123456",
            "Rs 5000 will be debited from your a/c for UPI mandate",
            "Rs 799 debited from a/c XX1234 via NEFT",
            "Rs 250.00 debited from a/c **1234 on 02-11-26 to VPA x@ybl UPI transaction failed",
            "Hello! Get 10% cashback on UPI payments this weekend",
            "",
        ):
            with self.assertRaises(SmsIgnored, msg=sms):
                parse_upi_sms(sms, TODAY)

    def test_future_date_is_not_trusted(self):
        p = parse_upi_sms("Rs 10 debited from a/c 1 on 02-11-31 to VPA a@b UPI Ref 312345678901".replace("a@b", "abc@ybl"), TODAY)
        self.assertIsNone(p.when)


class IngestApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="StrongPass123")
        self.client.force_authenticate(self.admin)
        self.key = self.client.post("/api/records/ingest/key/").json()["data"]["key"]
        self.client.force_authenticate(None)

    def send(self, sms, key=None, ctype="text/plain"):
        """Post like the phone does: only the ingest key, never a browser login."""
        self.client.force_authenticate(None)
        extra = {"HTTP_X_INGEST_KEY": self.key if key is None else key}
        try:
            if ctype == "json":
                return self.client.post("/api/records/ingest/sms/", {"message": sms}, format="json", **extra)
            return self.client.post("/api/records/ingest/sms/", sms, content_type="text/plain", **extra)
        finally:
            self.client.force_authenticate(self.admin if self.logged_in else None)

    logged_in = False

    def login(self):
        self.logged_in = True
        self.client.force_authenticate(self.admin)

    def test_key_is_required_and_only_a_hash_is_stored(self):
        self.assertEqual(self.send(HDFC_DEBIT, key="").status_code, 401)
        self.assertEqual(self.send(HDFC_DEBIT, key="fin_wrong").status_code, 401)
        self.assertEqual(Record.objects.count(), 0)
        from records.models import IngestKey
        self.assertNotIn(self.key, [k.key_hash for k in IngestKey.objects.all()])

    def test_creates_record_from_plain_text_and_json(self):
        res = self.send(HDFC_DEBIT)
        self.assertEqual(res.status_code, 201, res.content)
        data = res.json()["data"]
        self.assertEqual(data["status"], "created")
        r = Record.objects.get()
        self.assertEqual((r.type, r.amount, r.counterparty, r.kind, r.upi_ref), (EXPENSE, Decimal("250.00"), "Rahul Sharma", NORMAL, "312345678901"))
        self.assertEqual(r.user, self.admin)
        self.assertEqual(self.send(VPA_CREDIT.format(amt="75.00", ref="999999999999"), ctype="json").status_code, 201)
        self.assertEqual(Record.objects.count(), 2)

    def test_same_sms_twice_creates_one_record(self):
        self.assertEqual(self.send(HDFC_DEBIT).status_code, 201)
        res = self.send(HDFC_DEBIT)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["status"], "duplicate")
        self.assertEqual(Record.objects.count(), 1)

    def test_deleted_record_is_not_re_imported(self):
        self.send(HDFC_DEBIT)
        Record.objects.update(is_deleted=True)
        self.assertEqual(self.send(HDFC_DEBIT).json()["data"]["status"], "duplicate")
        self.assertEqual(Record.all_objects.count(), 1)

    def test_junk_sms_is_acknowledged_but_ignored(self):
        res = self.send("Your OTP for UPI txn is 123456")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["status"], "ignored")
        self.assertEqual(Record.objects.count(), 0)

    def test_preview_saves_nothing(self):
        self.login()
        res = self.client.post("/api/records/ingest/preview/", {"message": HDFC_DEBIT}, format="json").json()["data"]
        self.assertTrue(res["understood"])
        self.assertEqual((res["type"], res["amount"], res["counterparty"]), ("expense", "250.00", "Rahul Sharma"))
        self.assertEqual(Record.objects.count(), 0)

    def test_key_stops_working_if_owner_loses_admin(self):
        User.objects.filter(pk=self.admin.pk).update(role=ANALYST)
        self.assertEqual(self.send(HDFC_DEBIT).status_code, 403)
        self.assertEqual(Record.objects.count(), 0)

    def test_rotating_revokes_the_old_key(self):
        old = self.key
        self.login()
        self.key = self.client.post("/api/records/ingest/key/").json()["data"]["key"]
        self.client.force_authenticate(None)
        self.assertEqual(self.send(HDFC_DEBIT, key=old).status_code, 401)
        self.assertEqual(self.send(HDFC_DEBIT).status_code, 201)

    def test_key_is_scoped_to_its_own_workspace(self):
        other = self.client.post("/api/users/register/", {"workspace_name": "Other", "email": "o@o.com", "password": "StrongPass123"}, format="json")
        self.assertEqual(other.status_code, 201)
        self.send(HDFC_DEBIT)
        o = User.objects.get(email="o@o.com")
        self.assertEqual(Record.objects.filter(workspace=o.workspace).count(), 0)
        self.assertEqual(Record.objects.filter(workspace=self.admin.workspace).count(), 1)

    def test_friend_lending_and_repayment_flow(self):
        self.login()
        # 1. First payment to Rahul arrives as a normal expense; the owner marks him as a friend.
        self.send(VPA_DEBIT.format(ref="100000000001"))
        rec = Record.objects.get()
        res = self.client.patch(f"/api/records/{rec.id}/", {"kind": LENT, "counterparty": "rahul@okaxis", "category": "Friends"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        # 2. From now on payments to / from Rahul are classified automatically.
        self.send(VPA_DEBIT.format(ref="100000000002"))
        self.send(VPA_CREDIT.format(amt="300.00", ref="100000000003"))
        self.assertEqual(list(Record.objects.order_by("id").values_list("kind", flat=True)), [LENT, LENT, REPAYMENT])
        # 3. Ledger: lent 500, repaid 300 -> he still owes 200.
        friends = self.client.get("/api/dashboard/friends/").json()["data"]["friends"]
        self.assertEqual(friends["total_owed_to_me"], 200.0)
        self.assertEqual((friends["friends"][0]["name"], friends["friends"][0]["balance"]), ("rahul@okaxis", 200.0))
        # 4. He pays the rest back: settled, and nobody owes anybody.
        self.send(VPA_CREDIT.format(amt="200.00", ref="100000000004"))
        friends = self.client.get("/api/dashboard/friends/").json()["data"]["friends"]
        self.assertEqual((friends["total_owed_to_me"], friends["total_i_owe"], friends["friends"][0]["balance"]), (0.0, 0.0, 0.0))

    def test_friend_money_stays_out_of_income_expense_and_budgets(self):
        self.login()
        today = date.today().isoformat()
        base = {"date": today, "counterparty": "Sam"}
        self.client.post("/api/records/", {**base, "amount": "1000", "type": "expense", "category": "Friends", "kind": "lent"}, format="json")
        self.client.post("/api/records/", {**base, "amount": "1000", "type": "income", "category": "Friends", "kind": "repayment"}, format="json")
        self.client.post("/api/records/", {"date": today, "amount": "80", "type": "expense", "category": "Food"}, format="json")
        self.client.post("/api/records/", {"date": today, "amount": "500", "type": "income", "category": "Salary"}, format="json")
        s = self.client.get("/api/dashboard/summary/").json()["data"]
        self.assertEqual((s["summary"]["total_income"], s["summary"]["total_expense"], s["summary"]["transaction_count"]), (500.0, 80.0, 2))
        self.assertEqual(s["friends"]["friends"][0]["balance"], 0.0)
        self.client.post("/api/budgets/", {"category": "Friends", "monthly_limit": "100"}, format="json")
        b = self.client.get("/api/budgets/status/").json()["data"]["budgets"][0]
        self.assertEqual(b["spent"], 0.0)
        # The records list still shows everything.
        self.assertEqual(self.client.get("/api/records/").json()["data"]["count"], 4)

    def test_kind_rules_are_validated(self):
        self.login()
        base = {"date": "2026-01-01", "amount": "10", "category": "Friends"}
        bad = [
            {**base, "type": "income", "kind": "lent", "counterparty": "Sam"},
            {**base, "type": "expense", "kind": "repayment", "counterparty": "Sam"},
            {**base, "type": "expense", "kind": "lent"},  # no friend named
        ]
        for body in bad:
            self.assertEqual(self.client.post("/api/records/", body, format="json").status_code, 400, body)
        ok = self.client.post("/api/records/", {**base, "type": "expense", "kind": "lent", "counterparty": " Sam "}, format="json")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.json()["data"]["counterparty"], "Sam")
        # PATCHing only the type of a lent record must not silently break the rule.
        rid = ok.json()["data"]["id"]
        self.assertEqual(self.client.patch(f"/api/records/{rid}/", {"type": "income"}, format="json").status_code, 400)

    def test_csv_export_import_keeps_friend_info(self):
        self.login()
        self.client.post("/api/records/", {"date": "2026-01-01", "amount": "10", "type": "expense", "category": "Friends", "kind": "lent", "counterparty": "Sam"}, format="json")
        csv_text = self.client.get("/api/records/export/").content.decode()
        Record.objects.all().delete()
        self.assertEqual(self.client.post("/api/records/import/", {"csv": csv_text}, format="json").status_code, 201)
        r = Record.objects.get()
        self.assertEqual((r.kind, r.counterparty), (LENT, "Sam"))
