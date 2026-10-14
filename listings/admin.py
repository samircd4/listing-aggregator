from django.contrib import admin

from .models import ListingEvent, ListingSnapshot, SourceListing


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class EventInline(ReadOnlyInline):
    model = ListingEvent
    fields = ("occurred_at", "event_type", "field", "old_value", "new_value")


class SnapshotInline(ReadOnlyInline):
    model = ListingSnapshot
    fields = ("captured_at", "asking_price", "annual_revenue", "annual_profit", "profit_margin", "is_active")


@admin.register(SourceListing)
class SourceListingAdmin(admin.ModelAdmin):
    list_display = ("external_id", "short_name", "upstream_source", "asking_price", "currency", "data_quality", "is_active", "last_seen_at")
    list_filter = ("source", "upstream_source", "is_active", "data_quality", "currency")
    search_fields = ("name", "external_id", "upstream_id")
    readonly_fields = [f.name for f in SourceListing._meta.fields]  # pylint: disable=no-member
    inlines = [EventInline, SnapshotInline]

    @admin.display(description="Name")
    def short_name(self, obj):
        return obj.name[:70]
