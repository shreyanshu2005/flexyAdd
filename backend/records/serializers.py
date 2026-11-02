from __future__ import annotations

from rest_framework import serializers

from core.constants import EXPENSE, INCOME, LENT, NORMAL, RECORD_KIND_CHOICES, REPAYMENT
from records.models import Record
from records.services import RecordService


class RecordSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Record
        fields = ["id", "user_email", "amount", "type", "category", "date", "note", "kind", "counterparty", "upi_ref", "created_at"]
        read_only_fields = ["id", "user_email", "upi_ref", "created_at"]


class RecordWriteSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    type = serializers.ChoiceField(choices=[("income", "Income"), ("expense", "Expense")])
    category = serializers.CharField(max_length=100)
    date = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True)
    kind = serializers.ChoiceField(choices=RECORD_KIND_CHOICES, required=False)
    counterparty = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate(self, attrs):
        # On PATCH only some fields arrive, so fall back to what is already stored.
        current = lambda f, default: attrs.get(f, getattr(self.instance, f, default))  # noqa: E731
        kind, typ, who = current("kind", NORMAL), current("type", None), (current("counterparty", "") or "").strip()
        if kind == LENT and typ != EXPENSE:
            raise serializers.ValidationError({"kind": "Money lent to a friend must be an expense."})
        if kind == REPAYMENT and typ != INCOME:
            raise serializers.ValidationError({"kind": "A repayment from a friend must be income."})
        if kind != NORMAL and not who:
            raise serializers.ValidationError({"counterparty": "Say which friend this is (name or UPI id)."})
        if "counterparty" in attrs:
            attrs["counterparty"] = who
        return attrs

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def create(self, validated_data):
        return RecordService.create_record(self.context["request"].user, validated_data)

    def update(self, instance, validated_data):
        return RecordService.update_record(instance, validated_data)
