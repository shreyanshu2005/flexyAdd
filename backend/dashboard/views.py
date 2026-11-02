from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import IsViewerOrAbove
from core.responses import success_response
from dashboard.serializers import DashboardAnalyticsResponseSerializer, DashboardQuerySerializer
from dashboard.services import DashboardService


def dashboard_query_parameters():
    return [
        OpenApiParameter(
            name="start_date",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter records from this date (YYYY-MM-DD).",
        ),
        OpenApiParameter(
            name="end_date",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter records up to this date (YYYY-MM-DD).",
        ),
    ]


def dashboard_request_example(title: str):
    return OpenApiExample(
        f"{title} request",
        description="Typical analytics query window.",
        value={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        request_only=True,
    )


def dashboard_response_example(title: str, value: dict):
    return OpenApiExample(
        f"{title} response",
        description="Representative analytics payload.",
        value=value,
        response_only=True,
    )


class DashboardBaseAPIView(APIView):
    permission_classes = [IsAuthenticated, IsViewerOrAbove]
    throttle_scope = "dashboard"
    service_method = None
    page_title = "Dashboard analytics"

    def _get_data(self, request):
        serializer = DashboardQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        service_method = getattr(DashboardService, self.service_method)
        return service_method(request.user, serializer.validated_data)

    def get(self, request):
        data = self._get_data(request)
        return success_response(data)


class DashboardSummaryAPIView(DashboardBaseAPIView):
    service_method = "get_summary"
    page_title = "Dashboard summary and analytics"

    @extend_schema(
        tags=["Dashboard"],
        summary="Dashboard summary and analytics",
        description=(
            "Returns business-focused dashboard analytics including summary totals, period comparison, "
            "top spending categories, insights, monthly trends, and admin-only user breakdown."
        ),
        parameters=dashboard_query_parameters(),
        responses=DashboardAnalyticsResponseSerializer,
        examples=[
            dashboard_request_example("Dashboard summary"),
            dashboard_response_example(
                "Dashboard summary",
                {
                    "summary": {
                        "total_income": "1200.00",
                        "total_expense": "400.00",
                        "net_balance": "800.00",
                        "transaction_count": 4,
                    },
                    "period_comparison": {
                        "current_period": {"start_date": "2026-01-01", "end_date": "2026-01-31"},
                        "previous_period": {"start_date": "2025-12-01", "end_date": "2025-12-31"},
                    },
                    "top_spending_categories": [{"category": "Food", "total_amount": "250.00"}],
                    "insights": [
                        {
                            "type": "expense_spike",
                            "message": "Expenses are up 25.0% compared with the previous period.",
                        }
                    ],
                },
            ),
        ],
    )
    def get(self, request):
        return super().get(request)


class DashboardComparisonAPIView(DashboardBaseAPIView):
    service_method = "get_comparison"
    page_title = "Dashboard comparison"

    @extend_schema(
        tags=["Dashboard"],
        summary="Dashboard comparison",
        description="Compares the selected window against the immediately previous window.",
        parameters=dashboard_query_parameters(),
        responses=DashboardAnalyticsResponseSerializer,
        examples=[dashboard_request_example("Dashboard comparison")],
    )
    def get(self, request):
        return super().get(request)


class DashboardCategoryBreakdownAPIView(DashboardBaseAPIView):
    service_method = "get_category_breakdown"
    page_title = "Category breakdown"

    @extend_schema(
        tags=["Dashboard"],
        summary="Category breakdown",
        description="Shows category-wise totals and record counts for the selected window.",
        parameters=dashboard_query_parameters(),
        responses=DashboardAnalyticsResponseSerializer,
        examples=[dashboard_request_example("Category breakdown")],
    )
    def get(self, request):
        return super().get(request)


class DashboardTopSpendingAPIView(DashboardBaseAPIView):
    service_method = "get_top_spending_categories"
    page_title = "Top spending categories"

    @extend_schema(
        tags=["Dashboard"],
        summary="Top spending categories",
        description="Ranks the highest expense categories and their share of total expenses.",
        parameters=dashboard_query_parameters(),
        responses=DashboardAnalyticsResponseSerializer,
        examples=[dashboard_request_example("Top spending categories")],
    )
    def get(self, request):
        return super().get(request)


class DashboardTrendsAPIView(DashboardBaseAPIView):
    service_method = "get_monthly_trends"
    page_title = "Monthly trends"

    @extend_schema(
        tags=["Dashboard"],
        summary="Monthly trends",
        description="Shows monthly income and expense trends.",
        parameters=dashboard_query_parameters(),
        responses=DashboardAnalyticsResponseSerializer,
        examples=[dashboard_request_example("Monthly trends")],
    )
    def get(self, request):
        return super().get(request)


class DashboardInsightsAPIView(DashboardBaseAPIView):
    service_method = "get_insights"
    page_title = "Business insights"

    @extend_schema(
        tags=["Dashboard"],
        summary="Business insights",
        description="Returns rule-based insight flags such as spikes, concentration, or negative balance.",
        parameters=dashboard_query_parameters(),
        responses=DashboardAnalyticsResponseSerializer,
        examples=[dashboard_request_example("Business insights")],
    )
    def get(self, request):
        return super().get(request)


class DashboardUsersAPIView(DashboardBaseAPIView):
    service_method = "get_user_breakdown"
    page_title = "Admin user breakdown"

    @extend_schema(
        tags=["Dashboard"],
        summary="Admin user breakdown",
        description="Shows user-level contribution, only for admin users.",
        parameters=dashboard_query_parameters(),
        responses=DashboardAnalyticsResponseSerializer,
        examples=[dashboard_request_example("Admin user breakdown")],
    )
    def get(self, request):
        return super().get(request)


class DashboardFriendsAPIView(DashboardBaseAPIView):
    service_method = "get_friends"
    page_title = "Friends ledger"

    @extend_schema(
        tags=["Dashboard"],
        summary="Friends ledger",
        description="Per-friend balance of money lent minus money repaid (all time). Positive means they owe you.",
        responses=DashboardAnalyticsResponseSerializer,
    )
    def get(self, request):
        return super().get(request)
