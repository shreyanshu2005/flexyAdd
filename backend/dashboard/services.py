from __future__ import annotations

from decimal import Decimal
from datetime import timedelta

from django.db.models import Case, Count, DecimalField, F, Max, Min, Sum, Value, When
from django.db.models.functions import Lower, TruncMonth

from core.constants import ADMIN, ANALYST, EXPENSE, FRIEND_KINDS, INCOME, LENT, NORMAL, REPAYMENT, VIEWER
from records.models import Record


class DashboardService:
    @staticmethod
    def _base_queryset(user):
        if user.role not in {ADMIN, ANALYST, VIEWER}:
            return Record.objects.none()
        # Money lent to / repaid by friends is not income or spending, so it is excluded here.
        return Record.objects.active().select_related("user").filter(workspace_id=user.workspace_id, kind=NORMAL)

    @staticmethod
    def _zero():
        return Decimal("0.00")

    @classmethod
    def _apply_filters(cls, queryset, filters):
        if filters.get("start_date"):
            queryset = queryset.filter(date__gte=filters["start_date"])
        if filters.get("end_date"):
            queryset = queryset.filter(date__lte=filters["end_date"])
        return queryset

    @classmethod
    def _totals(cls, queryset):
        totals = queryset.aggregate(
            total_income=Sum(
                Case(
                    When(type=INCOME, then="amount"),
                    default=Value(cls._zero()),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            total_expense=Sum(
                Case(
                    When(type=EXPENSE, then="amount"),
                    default=Value(cls._zero()),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
        )
        total_income = totals["total_income"] or cls._zero()
        total_expense = totals["total_expense"] or cls._zero()
        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "net_balance": total_income - total_expense,
            "transaction_count": queryset.count(),
        }

    @staticmethod
    def _percentage_change(current, previous):
        if previous in {None, Decimal("0.00"), 0}:
            return None
        return ((current - previous) / previous) * Decimal("100")

    @classmethod
    def _period_comparison(cls, queryset, filters=None, user=None):
        filters = filters or {}
        bounds = queryset.aggregate(start_date=Min("date"), end_date=Max("date"))

        # Prefer explicitly requested date range so comparison windows are stable
        # even when records do not span the full selected period.
        requested_start = filters.get("start_date")
        requested_end = filters.get("end_date")

        if requested_start and requested_end:
            current_start = requested_start
            current_end = requested_end
        elif requested_start:
            current_start = requested_start
            current_end = bounds["end_date"] or requested_start
        elif requested_end:
            current_start = bounds["start_date"] or requested_end
            current_end = requested_end
        else:
            current_start = bounds["start_date"]
            current_end = bounds["end_date"]

        if not current_start or not current_end:
            empty_metrics = {"total_income": cls._zero(), "total_expense": cls._zero(), "net_balance": cls._zero(), "transaction_count": 0}
            return {
                "current_period": {"start_date": None, "end_date": None, **empty_metrics},
                "previous_period": {"start_date": None, "end_date": None, **empty_metrics},
                "change": {
                    "total_income": {"amount": cls._zero(), "percentage": None},
                    "total_expense": {"amount": cls._zero(), "percentage": None},
                    "net_balance": {"amount": cls._zero(), "percentage": None},
                    "transaction_count": {"amount": 0, "percentage": None},
                },
            }

        current_metrics = cls._totals(queryset)
        duration_days = (current_end - current_start).days + 1
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=duration_days - 1)
        previous_queryset = queryset.model.objects.active().select_related("user").filter(workspace_id=getattr(user, "workspace_id", None), kind=NORMAL, date__gte=previous_start, date__lte=previous_end)
        previous_metrics = cls._totals(previous_queryset)

        return {
            "current_period": {"start_date": current_start, "end_date": current_end, **current_metrics},
            "previous_period": {
                "start_date": previous_start,
                "end_date": previous_end,
                **previous_metrics,
            },
            "change": {
                "total_income": {
                    "amount": current_metrics["total_income"] - previous_metrics["total_income"],
                    "percentage": cls._percentage_change(current_metrics["total_income"], previous_metrics["total_income"]),
                },
                "total_expense": {
                    "amount": current_metrics["total_expense"] - previous_metrics["total_expense"],
                    "percentage": cls._percentage_change(current_metrics["total_expense"], previous_metrics["total_expense"]),
                },
                "net_balance": {
                    "amount": current_metrics["net_balance"] - previous_metrics["net_balance"],
                    "percentage": cls._percentage_change(current_metrics["net_balance"], previous_metrics["net_balance"]),
                },
                "transaction_count": {
                    "amount": current_metrics["transaction_count"] - previous_metrics["transaction_count"],
                    "percentage": cls._percentage_change(
                        Decimal(current_metrics["transaction_count"]),
                        Decimal(previous_metrics["transaction_count"]),
                    ),
                },
            },
        }

    @classmethod
    def _top_spending_categories(cls, queryset, total_expense):
        categories = list(
            queryset.filter(type=EXPENSE)
            .values("category")
            .annotate(
                total_amount=Sum("amount"),
                record_count=Count("id"),
            )
            .order_by("-total_amount", "category")[:5]
        )
        for category in categories:
            amount = category["total_amount"] or cls._zero()
            category["share_of_expenses"] = (
                (amount / total_expense) * Decimal("100") if total_expense else None
            )
        return categories

    @classmethod
    def _insights(cls, summary, comparison, top_categories):
        insights = []
        current_expense = summary["total_expense"]
        previous_expense = comparison["previous_period"]["total_expense"]
        current_income = summary["total_income"]
        previous_income = comparison["previous_period"]["total_income"]

        if top_categories:
            lead_category = top_categories[0]
            if lead_category["share_of_expenses"] is not None and lead_category["share_of_expenses"] >= Decimal("40"):
                insights.append(
                    {
                        "type": "expense_concentration",
                        "message": (
                            f"{lead_category['category']} accounts for {lead_category['share_of_expenses']:.1f}% of total expenses."
                        ),
                    }
                )

        expense_change = cls._percentage_change(current_expense, previous_expense)
        if expense_change is not None and expense_change >= Decimal("20"):
            insights.append(
                {
                    "type": "expense_spike",
                    "message": f"Expenses are up {expense_change:.1f}% compared with the previous period.",
                }
            )

        income_change = cls._percentage_change(current_income, previous_income)
        if income_change is not None and income_change >= Decimal("20"):
            insights.append(
                {
                    "type": "income_growth",
                    "message": f"Income is up {income_change:.1f}% compared with the previous period.",
                }
            )

        if summary["net_balance"] < 0:
            insights.append(
                {
                    "type": "negative_balance",
                    "message": "Net balance is negative for the selected period.",
                }
            )

        return insights

    @classmethod
    def _user_breakdown(cls, queryset):
        users = list(
            queryset.values("user_id", user_email=F("user__email"))
            .annotate(
                total_income=Sum(
                    Case(
                        When(type=INCOME, then="amount"),
                        default=Value(cls._zero()),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                total_expense=Sum(
                    Case(
                        When(type=EXPENSE, then="amount"),
                        default=Value(cls._zero()),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                transaction_count=Count("id"),
            )
            .order_by("-total_expense", "-transaction_count", "user_email")
        )
        for row in users:
            total_income = row["total_income"] or cls._zero()
            total_expense = row["total_expense"] or cls._zero()
            row["net_balance"] = total_income - total_expense
        return users

    @classmethod
    def _friend_balances(cls, user):
        """Per-person running balance: positive = they owe you, negative = you owe them. All-time, not date-filtered."""
        if user.role not in {ADMIN, ANALYST, VIEWER}:
            return {"friends": [], "total_owed_to_me": cls._zero(), "total_i_owe": cls._zero()}
        money = DecimalField(max_digits=12, decimal_places=2)
        rows = (
            Record.objects.active()
            .filter(workspace_id=user.workspace_id, kind__in=FRIEND_KINDS)
            .annotate(person=Lower("counterparty"))
            .values("person")
            .annotate(
                name=Max("counterparty"),
                lent=Sum(Case(When(kind=LENT, then="amount"), default=Value(cls._zero()), output_field=money)),
                repaid=Sum(Case(When(kind=REPAYMENT, then="amount"), default=Value(cls._zero()), output_field=money)),
                last_date=Max("date"),
            )
        )
        friends = []
        for r in rows:
            lent, repaid = r["lent"] or cls._zero(), r["repaid"] or cls._zero()
            friends.append({"name": r["name"], "lent": lent, "repaid": repaid, "balance": lent - repaid, "last_date": r["last_date"]})
        friends.sort(key=lambda f: (-abs(f["balance"]), f["name"].lower()))
        return {
            "friends": friends,
            "total_owed_to_me": sum((f["balance"] for f in friends if f["balance"] > 0), cls._zero()),
            "total_i_owe": sum((-f["balance"] for f in friends if f["balance"] < 0), cls._zero()),
        }

    @classmethod
    def get_friends(cls, user, filters):
        return {"friends": cls._friend_balances(user)}

    @classmethod
    def get_summary(cls, user, filters):
        queryset = cls._apply_filters(cls._base_queryset(user), filters)
        summary = cls._totals(queryset)
        comparison = cls._period_comparison(queryset, filters, user)
        top_categories = cls._top_spending_categories(queryset, summary["total_expense"])

        recent_transactions = list(
            queryset.order_by("-date", "-created_at").values(
                "id",
                "amount",
                "type",
                "category",
                "date",
                "note",
                "created_at",
                user_email=F("user__email"),
            )[:5]
        )

        monthly_trends = list(
            queryset.annotate(month=TruncMonth("date")).values("month").annotate(
                income=Sum(Case(When(type=INCOME, then="amount"), default=Value(Decimal("0.00")), output_field=DecimalField(max_digits=12, decimal_places=2))),
                expense=Sum(Case(When(type=EXPENSE, then="amount"), default=Value(Decimal("0.00")), output_field=DecimalField(max_digits=12, decimal_places=2))),
            ).order_by("month")
        )

        user_breakdown = cls._user_breakdown(queryset) if user.role == ADMIN else []

        return {
            "summary": summary,
            "period_comparison": comparison,
            "category_breakdown": list(
                queryset.values("category").annotate(
                    total_amount=Sum("amount"),
                    record_count=Count("id"),
                ).order_by("-total_amount", "category")
            ),
            "top_spending_categories": top_categories,
            "recent_transactions": recent_transactions,
            "monthly_trends": monthly_trends,
            "insights": cls._insights(summary, comparison, top_categories),
            "user_breakdown": user_breakdown,
            "friends": cls._friend_balances(user),
        }

    @classmethod
    def get_comparison(cls, user, filters):
        queryset = cls._apply_filters(cls._base_queryset(user), filters)
        comparison = cls._period_comparison(queryset, filters, user)
        return {"period_comparison": comparison}

    @classmethod
    def get_category_breakdown(cls, user, filters):
        queryset = cls._apply_filters(cls._base_queryset(user), filters)
        return {
            "category_breakdown": list(
                queryset.values("category").annotate(
                    total_amount=Sum("amount"),
                    record_count=Count("id"),
                ).order_by("-total_amount", "category")
            )
        }

    @classmethod
    def get_top_spending_categories(cls, user, filters):
        queryset = cls._apply_filters(cls._base_queryset(user), filters)
        summary = cls._totals(queryset)
        return {"top_spending_categories": cls._top_spending_categories(queryset, summary["total_expense"])}

    @classmethod
    def get_monthly_trends(cls, user, filters):
        queryset = cls._apply_filters(cls._base_queryset(user), filters)
        return {
            "monthly_trends": list(
                queryset.annotate(month=TruncMonth("date")).values("month").annotate(
                    income=Sum(
                        Case(
                            When(type=INCOME, then="amount"),
                            default=Value(Decimal("0.00")),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        )
                    ),
                    expense=Sum(
                        Case(
                            When(type=EXPENSE, then="amount"),
                            default=Value(Decimal("0.00")),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        )
                    ),
                ).order_by("month")
            )
        }

    @classmethod
    def get_insights(cls, user, filters):
        queryset = cls._apply_filters(cls._base_queryset(user), filters)
        summary = cls._totals(queryset)
        comparison = cls._period_comparison(queryset, filters, user)
        top_categories = cls._top_spending_categories(queryset, summary["total_expense"])
        return {"insights": cls._insights(summary, comparison, top_categories)}

    @classmethod
    def get_user_breakdown(cls, user, filters):
        if user.role != ADMIN:
            return {"user_breakdown": []}
        queryset = cls._apply_filters(cls._base_queryset(user), filters)
        return {"user_breakdown": cls._user_breakdown(queryset)}
