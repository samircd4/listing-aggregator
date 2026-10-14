from django.contrib import admin

from .models import IngestionRun


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ("source", "started_at", "status", "complete", "seen_count", "new_count", "changed_count", "removed_count", "failed_count")
    list_filter = ("source", "status", "complete")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
