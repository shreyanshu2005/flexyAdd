from django_filters import rest_framework as filters

from records.models import Record


class RecordFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name="date", lookup_expr="gte")
    end_date = filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = Record
        fields = ["category", "type", "start_date", "end_date"]
