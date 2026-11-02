from __future__ import annotations

from django.db import transaction
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsAdminRole, IsAnalystOrAdmin
from core.responses import success_response
from records.csv_io import export_csv, parse_csv
from records.filters import RecordFilter
from records.nlp import parse_entry
from records.models import Record
from records.serializers import RecordSerializer, RecordWriteSerializer
from records.services import RecordService


@extend_schema_view(
    create=extend_schema(tags=["Records"], summary="Create record"),
    list=extend_schema(tags=["Records"], summary="List records"),
    retrieve=extend_schema(tags=["Records"], summary="Get record"),
    update=extend_schema(tags=["Records"], summary="Update record"),
    partial_update=extend_schema(tags=["Records"], summary="Partially update record"),
    destroy=extend_schema(tags=["Records"], summary="Delete record"),
)
class RecordViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Record.objects.select_related("user").active()
    filterset_class = RecordFilter
    search_fields = ["note", "category"]
    ordering_fields = ["date", "created_at", "amount"]
    throttle_scope = "records"

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "import_csv", "parse"}:
            permission_classes = [IsAuthenticated, IsAdminRole]
        else:
            permission_classes = [IsAuthenticated, IsAnalystOrAdmin]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return RecordWriteSerializer
        return RecordSerializer

    def get_queryset(self):
        return RecordService.build_queryset(self.request.user, self.request.query_params)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = RecordSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = RecordSerializer(queryset, many=True)
        return success_response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        record = self.get_object()
        return success_response(RecordSerializer(record).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return success_response(RecordSerializer(record).data, status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        record = self.get_object()
        serializer = self.get_serializer(record, data=request.data, partial=kwargs.get("partial", False), context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated_record = serializer.save()
        return success_response(RecordSerializer(updated_record).data)

    def destroy(self, request, *args, **kwargs):
        record = self.get_object()
        RecordService.soft_delete_record(record)
        return success_response({"deleted": True})

    @extend_schema(tags=["Records"], summary="Turn a sentence like 'spent 450 on lunch yesterday' into a record suggestion (admin)")
    @action(detail=False, methods=["post"], url_path="parse")
    def parse(self, request):
        text = str(request.data.get("text") or "").strip()
        if not text or len(text) > 300:
            raise ValidationError({"text": "Enter a short description, e.g. spent 450 on lunch yesterday"})
        return success_response(parse_entry(text, request.user.workspace_id))

    @extend_schema(tags=["Records"], summary="Export filtered records as CSV (analyst/admin)")
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        response = HttpResponse(export_csv(queryset), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="records.csv"'
        return response

    @extend_schema(tags=["Records"], summary="Bulk import records from CSV text (admin, all-or-nothing)")
    @action(detail=False, methods=["post"], url_path="import")
    def import_csv(self, request):
        rows, errors = parse_csv(request.data.get("csv", ""), request)
        if errors:
            raise ValidationError({"csv": errors[:20] + ([f"...and {len(errors) - 20} more"] if len(errors) > 20 else [])})
        if not rows:
            raise ValidationError({"csv": "No data rows found."})
        with transaction.atomic():
            for data in rows:
                RecordService.create_record(request.user, data)
        return success_response({"imported": len(rows)}, status_code=status.HTTP_201_CREATED)
