from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from core.constants import EXPENSE, NORMAL
from core.permissions import IsAdminRole, IsViewerOrAbove
from core.responses import success_response
from records.models import Budget, Record
from records.services import RecordService


class BudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Budget
        fields = ["id", "category", "monthly_limit"]


class BudgetViewSet(viewsets.GenericViewSet):
    serializer_class = BudgetSerializer
    throttle_scope = "records"

    def get_permissions(self):
        role = IsAdminRole if self.action in {"create", "destroy"} else IsViewerOrAbove
        return [IsAuthenticated(), role()]

    def get_queryset(self):
        return Budget.objects.filter(workspace_id=self.request.user.workspace_id).order_by("category")

    def list(self, request):
        return success_response(BudgetSerializer(self.get_queryset(), many=True).data)

    def create(self, request):
        """Set (or update) the monthly limit for a category."""
        serializer = BudgetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ws = request.user.workspace_id
        category = RecordService.canonical_category(ws, serializer.validated_data["category"])
        budget, _ = Budget.objects.update_or_create(
            workspace_id=ws, category=category, defaults={"monthly_limit": serializer.validated_data["monthly_limit"]}
        )
        return success_response(BudgetSerializer(budget).data, status_code=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        self.get_object().delete()
        return success_response({"deleted": True})

    @action(detail=False, methods=["get"], url_path="status")
    def budget_status(self, request):
        """Spend vs. limit per budget for a month (?month=YYYY-MM), plus human-readable alerts."""
        month = request.query_params.get("month") or date.today().strftime("%Y-%m")
        try:
            year, mon = (int(x) for x in month.split("-"))
            first = date(year, mon, 1)
        except ValueError:
            raise ValidationError({"month": "Use YYYY-MM."})
        nxt = date(year + (mon == 12), mon % 12 + 1, 1)
        spent: dict[str, Decimal] = {}
        rows = (
            Record.objects.active()
            .filter(workspace_id=request.user.workspace_id, type=EXPENSE, kind=NORMAL, date__gte=first, date__lt=nxt)
            .values("category")
            .annotate(total=Sum("amount"))
        )
        for row in rows:
            key = row["category"].lower()
            spent[key] = spent.get(key, Decimal("0")) + row["total"]
        budgets, alerts = [], []
        for b in self.get_queryset():
            used, limit = spent.get(b.category.lower(), Decimal("0")), b.monthly_limit
            pct = int(used / limit * 100)
            state = "over" if used > limit else "warn" if pct >= 80 else "ok"
            budgets.append({"id": b.id, "category": b.category, "limit": float(limit), "spent": float(used), "percent": pct, "state": state})
            if state == "over":
                alerts.append(f"{b.category} is over budget: {used:.2f} of {limit:.2f}")
            elif state == "warn":
                alerts.append(f"{b.category} has used {pct}% of its monthly budget")
        return success_response({"month": month, "budgets": budgets, "alerts": alerts})
