from django.db import models


class Source(models.Model):
    class Kind(models.TextChoices):
        API = "api", "API"
        FEED = "feed", "Feed"
        SCRAPER = "scraper", "Scraper"

    class Health(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        HEALTHY = "healthy", "Healthy"
        WARNING = "warning", "Warning"
        FAILING = "failing", "Failing"

    slug = models.SlugField(unique=True, help_text="Must match the connector slug.")
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.API)
    enabled = models.BooleanField(default=False)
    run_every_minutes = models.PositiveIntegerField(default=360)
    max_requests_per_minute = models.PositiveIntegerField(default=55)

    # Rights notes (fill in after reading the source's terms)
    may_display = models.BooleanField(default=False)
    may_index = models.BooleanField(default=False)
    attribution_required = models.BooleanField(default=False)
    retention_days = models.PositiveIntegerField(null=True, blank=True)
    rights_notes = models.TextField(blank=True)

    # Health (updated by the runner)
    health = models.CharField(max_length=20, choices=Health.choices, default=Health.UNKNOWN)
    consecutive_failures = models.PositiveSmallIntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}"
