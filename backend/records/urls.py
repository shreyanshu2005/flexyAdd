from django.urls import include, path
from rest_framework.routers import DefaultRouter

from records.ingest_views import IngestKeyView, IngestPreviewView, IngestSmsView
from records.views import RecordViewSet

router = DefaultRouter()
router.register(r"", RecordViewSet, basename="records")

urlpatterns = [
    path("ingest/sms/", IngestSmsView.as_view(), name="ingest-sms"),
    path("ingest/preview/", IngestPreviewView.as_view(), name="ingest-preview"),
    path("ingest/key/", IngestKeyView.as_view(), name="ingest-key"),
    path("", include(router.urls)),
]
