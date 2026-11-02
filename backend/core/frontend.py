from pathlib import Path

from django.conf import settings
from django.http import HttpResponse


def app(request):
    """Serve the single-file dashboard UI (same origin as the API, so no CORS needed)."""
    page = Path(settings.BASE_DIR) / "frontend" / "index.html"
    return HttpResponse(page.read_text(encoding="utf-8"), content_type="text/html")
