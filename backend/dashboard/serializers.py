from __future__ import annotations

from rest_framework import serializers


class DashboardQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": "end_date must be greater than or equal to start_date."})
        return attrs


class DashboardAnalyticsResponseSerializer(serializers.Serializer):
    summary = serializers.JSONField(required=False)
    period_comparison = serializers.JSONField(required=False)
    category_breakdown = serializers.JSONField(required=False)
    top_spending_categories = serializers.JSONField(required=False)
    recent_transactions = serializers.JSONField(required=False)
    monthly_trends = serializers.JSONField(required=False)
    insights = serializers.JSONField(required=False)
    user_breakdown = serializers.JSONField(required=False)
    friends = serializers.JSONField(required=False)
