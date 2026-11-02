from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.constants import ADMIN, ANALYST, EXPENSE, INCOME
from records.models import Record


class RecordService:
    @staticmethod
    def visible_queryset(user):
        if user.role not in {ADMIN, ANALYST}:
            raise PermissionDenied("You do not have access to financial records.")
        return Record.objects.select_related("user").active().filter(workspace_id=user.workspace_id)

    @staticmethod
    def canonical_category(workspace_id, name):
        """'salary', 'Salary ' and 'SALARY' all collapse to the first spelling used in the workspace."""
        name = " ".join((name or "").split())
        existing = Record.all_objects.filter(workspace_id=workspace_id, category__iexact=name).values_list("category", flat=True).first()
        return existing or name

    @classmethod
    def build_queryset(cls, user, filters):
        queryset = cls.visible_queryset(user)
        search = filters.get("search")
        if search:
            queryset = queryset.filter(Q(note__icontains=search) | Q(category__icontains=search))
        return queryset

    @classmethod
    @transaction.atomic
    def create_record(cls, user, data):
        if user.role != ADMIN:
            raise PermissionDenied("Only admins can create records.")
        if data["type"] not in {INCOME, EXPENSE}:
            raise ValidationError({"type": "Invalid transaction type."})
        data = {**data, "category": cls.canonical_category(user.workspace_id, data["category"])}
        return Record.objects.create(user=user, workspace_id=user.workspace_id, **data)

    @classmethod
    @transaction.atomic
    def update_record(cls, record, data):
        if "category" in data:
            data = {**data, "category": cls.canonical_category(record.workspace_id, data["category"])}
        for field, value in data.items():
            setattr(record, field, value)
        record.full_clean()
        record.save()
        return record

    @classmethod
    @transaction.atomic
    def soft_delete_record(cls, record):
        if record.is_deleted:
            return record
        record.is_deleted = True
        record.save(update_fields=["is_deleted"])
        return record
