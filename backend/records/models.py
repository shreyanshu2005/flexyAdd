from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from core.constants import NORMAL, RECORD_KIND_CHOICES, TRANSACTION_TYPE_CHOICES


class RecordQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)


class Record(models.Model):
    workspace = models.ForeignKey("users.Workspace", null=True, on_delete=models.PROTECT, related_name="records")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="records")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    type = models.CharField(max_length=16, choices=TRANSACTION_TYPE_CHOICES, db_index=True)
    category = models.CharField(max_length=100, db_index=True)
    date = models.DateField(db_index=True)
    note = models.TextField(blank=True, default="")
    kind = models.CharField(max_length=16, choices=RECORD_KIND_CHOICES, default=NORMAL, db_index=True)
    counterparty = models.CharField(max_length=120, blank=True, default="")
    upi_ref = models.CharField(max_length=64, blank=True, default="")
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = RecordQuerySet.as_manager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["category", "type"]),
            models.Index(fields=["is_deleted", "date"]),
            models.Index(fields=["workspace", "date"]),
            models.Index(fields=["workspace", "kind", "counterparty"]),
        ]
        constraints = [
            models.CheckConstraint(check=Q(amount__gt=0), name="record_amount_positive"),
            # The same UPI transaction can never be imported twice into one workspace.
            models.UniqueConstraint(fields=["workspace", "upi_ref"], condition=~Q(upi_ref=""), name="unique_upi_ref_per_workspace"),
        ]

    def save(self, *args, **kwargs):
        if self.workspace_id is None and self.user_id:
            self.workspace_id = self.user.workspace_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.email} {self.type} {self.amount}"


class Budget(models.Model):
    workspace = models.ForeignKey("users.Workspace", on_delete=models.CASCADE, related_name="budgets")
    category = models.CharField(max_length=100)
    monthly_limit = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "category"], name="unique_budget_per_category")]


class IngestKey(models.Model):
    """Secret that lets a phone post bank SMS to this workspace. Only a hash is stored."""

    workspace = models.ForeignKey("users.Workspace", on_delete=models.CASCADE, related_name="ingest_keys")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ingest_keys")
    key_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
