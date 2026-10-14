from django.db import models
from django.utils import timezone


class IngestionRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    source = models.ForeignKey("sources.Source", on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    complete = models.BooleanField(default=False, help_text="True if the whole source was read.")
    expected_total = models.PositiveIntegerField(null=True, blank=True)
    seen_count = models.PositiveIntegerField(default=0)
    new_count = models.PositiveIntegerField(default=0)
    changed_count = models.PositiveIntegerField(default=0)
    removed_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.source} {self.started_at:%Y-%m-%d %H:%M} ({self.status})"
