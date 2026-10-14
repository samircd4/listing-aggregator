from django.contrib import admin

from .models import Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "kind", "enabled", "run_every_minutes", "health", "last_success_at")
    list_editable = ("enabled", "run_every_minutes")
    readonly_fields = ("health", "consecutive_failures", "last_run_at", "last_success_at")
