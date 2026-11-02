from __future__ import annotations

import logging
import time


logger = logging.getLogger("finance_dashboard.request")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - started_at) * 1000
        user_identifier = getattr(getattr(request, "user", None), "email", "anonymous")
        logger.info(
            "%s %s %s user=%s duration_ms=%.2f",
            request.method,
            request.path,
            response.status_code,
            user_identifier,
            duration_ms,
        )
        return response
