from django.urls import path

from dashboard.views import (
    DashboardCategoryBreakdownAPIView,
    DashboardComparisonAPIView,
    DashboardFriendsAPIView,
    DashboardInsightsAPIView,
    DashboardSummaryAPIView,
    DashboardTopSpendingAPIView,
    DashboardTrendsAPIView,
    DashboardUsersAPIView,
)

urlpatterns = [
    path("summary/", DashboardSummaryAPIView.as_view(), name="dashboard-summary"),
    path("comparison/", DashboardComparisonAPIView.as_view(), name="dashboard-comparison"),
    path("categories/", DashboardCategoryBreakdownAPIView.as_view(), name="dashboard-categories"),
    path("top-spending/", DashboardTopSpendingAPIView.as_view(), name="dashboard-top-spending"),
    path("trends/", DashboardTrendsAPIView.as_view(), name="dashboard-trends"),
    path("insights/", DashboardInsightsAPIView.as_view(), name="dashboard-insights"),
    path("users/", DashboardUsersAPIView.as_view(), name="dashboard-users"),
    path("friends/", DashboardFriendsAPIView.as_view(), name="dashboard-friends"),
]
