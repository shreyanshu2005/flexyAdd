from __future__ import annotations

from django.http import Http404
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _flatten_error_details(detail):
    if isinstance(detail, dict):
        return {key: _flatten_error_details(value) for key, value in detail.items()}
    if isinstance(detail, list):
        return [_flatten_error_details(value) for value in detail]
    if isinstance(detail, ErrorDetail):
        return str(detail)
    return detail


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        if isinstance(exc, Http404):
            return Response(
                {"success": False, "data": None, "error": {"message": "Not found", "details": None}},
                status=404,
            )
        return Response(
            {"success": False, "data": None, "error": {"message": "Server error", "details": None}},
            status=500,
        )

    if isinstance(exc, ValidationError):
        message = "Validation failed"
        details = _flatten_error_details(response.data)
    else:
        message = "Request failed"
        details = _flatten_error_details(response.data)

    response.data = {"success": False, "data": None, "error": {"message": message, "details": details}}
    return response
