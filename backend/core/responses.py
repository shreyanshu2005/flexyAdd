from __future__ import annotations

from rest_framework.response import Response


def success_response(data=None, status_code=200):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def error_response(message, details=None, status_code=400):
    return Response(
        {"success": False, "data": None, "error": {"message": message, "details": details}},
        status=status_code,
    )
