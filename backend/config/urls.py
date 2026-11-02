from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.frontend import app
from core.views import health_check, root_endpoint
from users.views import CustomTokenObtainPairView, CustomTokenRefreshView

urlpatterns = [
    path("", root_endpoint, name="root"),
    path("app/", app, name="frontend"),
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("api/users/", include("users.urls")),
    path("api/records/", include("records.urls")),
    path("api/budgets/", include("records.budget_urls")),
    path("api/dashboard/", include("dashboard.urls")),
]
