from django.contrib import admin

from users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "created_at")
    search_fields = ("email",)
    ordering = ("-created_at",)
