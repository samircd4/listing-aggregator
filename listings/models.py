from django.db import models
from django.utils import timezone

MONEY = {"max_digits": 16, "decimal_places": 2, "null": True, "blank": True}


class SourceListing(models.Model):
    source = models.ForeignKey("sources.Source", on_delete=models.PROTECT, related_name="listings")
    external_id = models.CharField(max_length=64)
    upstream_source = models.CharField(max_length=64, blank=True, db_index=True)
    upstream_id = models.CharField(max_length=128, blank=True)

    name = models.TextField()
    url = models.URLField(max_length=1000, blank=True)
    listing_type = models.CharField(max_length=32, blank=True)
    industry = models.CharField(max_length=500, blank=True)
    language = models.CharField(max_length=8, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    age_years = models.PositiveSmallIntegerField(null=True, blank=True)
    thumbnail_url = models.URLField(max_length=1000, blank=True)

    asking_price = models.DecimalField(**MONEY)
    annual_revenue = models.DecimalField(**MONEY)
    monthly_revenue = models.DecimalField(**MONEY)
    annual_profit = models.DecimalField(**MONEY)
    profit_margin = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    profit_multiple = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    revenue_multiple = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    data_quality = models.CharField(max_length=20, default="as_given")  # as_given / corrected

    source_created_at = models.DateTimeField(null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)

    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    missed_runs = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    fingerprint = models.CharField(max_length=64, blank=True, db_index=True)  # Phase 2 matching
    content_hash = models.CharField(max_length=64, blank=True)
    raw = models.JSONField(default=dict)  # latest raw record

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], name="uniq_listing_per_source"),
        ]
        indexes = [models.Index(fields=["source", "is_active"])]

    def __str__(self):
        return f"{self.source} #{self.external_id}"


class ListingSnapshot(models.Model):
    """Append-only. A row is written whenever tracked fields change."""

    listing = models.ForeignKey(SourceListing, on_delete=models.CASCADE, related_name="snapshots")
    run = models.ForeignKey("ingestion.IngestionRun", null=True, on_delete=models.SET_NULL)
    captured_at = models.DateTimeField(default=timezone.now)
    asking_price = models.DecimalField(**MONEY)
    annual_revenue = models.DecimalField(**MONEY)
    annual_profit = models.DecimalField(**MONEY)
    profit_margin = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    content_hash = models.CharField(max_length=64)
    raw = models.JSONField(default=dict)

    class Meta:
        ordering = ["-captured_at"]


class ListingEvent(models.Model):
    """Append-only. Plain milestones in a listing's life."""

    class Type(models.TextChoices):
        LISTED = "listed", "Listed"
        PRICE_REDUCED = "price_reduced", "Price reduced"
        PRICE_INCREASED = "price_increased", "Price increased"
        DETAILS_CHANGED = "details_changed", "Details changed"
        REMOVED = "removed", "Removed"
        RELISTED = "relisted", "Relisted"

    listing = models.ForeignKey(SourceListing, on_delete=models.CASCADE, related_name="events")
    run = models.ForeignKey("ingestion.IngestionRun", null=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=30, choices=Type.choices)
    field = models.CharField(max_length=50, blank=True)
    old_value = models.CharField(max_length=255, blank=True)
    new_value = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-occurred_at"]
