from django.contrib import admin

from records.models import Record


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "type", "category", "date", "is_deleted", "created_at")
    list_filter = ("type", "category", "is_deleted", "date", "created_at")
    search_fields = ("note", "category", "user__email")
    ordering = ("-date",)
