from __future__ import annotations

from datetime import datetime

from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.permissions import IsAdminRole
from core.responses import success_response
from records.ingest import IngestKeyService, describe, ingest_sms, today_local
from records.models import IngestKey
from records.serializers import RecordSerializer
from records.sms_parser import MAX_SMS_CHARS, SmsIgnored, parse_upi_sms


def _read_sms(request):
    """Accepts raw text/plain (easiest for SMS-forwarder apps: no JSON escaping), JSON or form data."""
    ctype = (request.content_type or "").split(";")[0].strip().lower()
    if ctype == "text/plain":
        return request._request.body.decode("utf-8", "replace"), None
    data = request.data
    text = str(data.get("message") or data.get("text") or data.get("body") or "")
    received = None
    if data.get("received_at"):
        try:
            received = datetime.fromisoformat(str(data["received_at"]).replace("Z", "+00:00")).date()
        except ValueError:
            raise ValidationError({"received_at": "Use an ISO date/time, e.g. 2026-11-02T14:30:00."})
    return text, received


class IngestKeyAuthentication(BaseAuthentication):
    """Phone-side auth: the X-Ingest-Key header identifies the workspace (request.auth) and the admin who made the key."""

    def authenticate(self, request):
        raw = request.META.get("HTTP_X_INGEST_KEY")
        if not raw:
            return None
        key = IngestKeyService.authenticate(raw)
        if key is None:
            raise AuthenticationFailed("Invalid ingest key.")
        return key.user, key

    def authenticate_header(self, request):
        return "X-Ingest-Key"  # makes DRF answer 401 (not 403) when the key is missing


class IngestSmsView(APIView):
    """Called by the phone, not a logged-in browser."""

    authentication_classes = [IngestKeyAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ingest"

    def post(self, request):
        key = request.auth
        if not isinstance(key, IngestKey):  # e.g. a browser JWT: this endpoint is only for the phone's key
            raise AuthenticationFailed("Invalid ingest key.")
        text, received = _read_sms(request)
        if len(text) > MAX_SMS_CHARS:
            raise ValidationError({"message": "Message too long."})
        result, payload = ingest_sms(key, text, received)
        if result == "created":
            return success_response({"status": "created", "record": RecordSerializer(payload["record"]).data}, status.HTTP_201_CREATED)
        return success_response({"status": result, **payload})


class IngestPreviewView(APIView):
    """Admin-only dry run: shows how an SMS would be read, without saving anything."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    throttle_scope = "records"

    def post(self, request):
        text = str(request.data.get("message") or "")
        try:
            parsed = parse_upi_sms(text, today_local())
        except SmsIgnored as exc:
            return success_response({"understood": False, "reason": str(exc)})
        return success_response({"understood": True, **describe(parsed, parsed.when or today_local())})


class IngestKeyView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    throttle_scope = "records"

    @staticmethod
    def _info(user):
        key = IngestKey.objects.filter(workspace_id=user.workspace_id).first()
        if not key:
            return {"configured": False}
        return {"configured": True, "prefix": key.prefix, "created_at": key.created_at, "last_used_at": key.last_used_at}

    def get(self, request):
        return success_response(self._info(request.user))

    def post(self, request):
        raw = IngestKeyService.rotate(request.user)
        return success_response({**self._info(request.user), "key": raw}, status.HTTP_201_CREATED)

    def delete(self, request):
        IngestKey.objects.filter(workspace_id=request.user.workspace_id).delete()
        return success_response({"configured": False})
