from django.contrib import admin, messages

from ingestion.tasks import is_running, run_source_task

from .models import Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "kind", "enabled",
                    "run_every_minutes", "health", "last_success_at")
    list_editable = ("enabled", "run_every_minutes")
    readonly_fields = ("health", "consecutive_failures",
                       "last_run_at", "last_success_at")
    actions = ["run_now"]

    @admin.action(description="Run selected sources now")
    def run_now(self, request, queryset):
        started, busy = [], []
        for source in queryset:
            if is_running(source):
                busy.append(source.name)
            else:
                run_source_task.delay(source.pk)  # type: ignore
                started.append(source.name)
        if started:
            self.message_user(request, "Run requested for: " + ", ".join(started)
                              + ". Check Ingestion runs.")
        if busy:
            self.message_user(request, "Already running, not started: " + ", ".join(busy),
                              level=messages.WARNING)
