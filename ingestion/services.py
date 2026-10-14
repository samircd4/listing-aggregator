import hashlib
import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ingestion.connectors import get_connector
from ingestion.models import IngestionRun
from listings.models import ListingEvent, ListingSnapshot, SourceListing
from sources.models import Source

logger = logging.getLogger(__name__)

TRACKED_FIELDS = [
    "asking_price", "annual_revenue", "annual_profit", "profit_margin",
    "name", "listing_type", "industry",
]
REMOVE_AFTER_MISSED_RUNS = 2   # complete runs in a row that must miss a listing
MAX_FAILED_SHARE = 0.02        # more bad records than this makes the run "partial"
FAILING_AFTER = 3              # bad runs in a row


def _s(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def _hash(std):
    text = "|".join(_s(getattr(std, f)) for f in TRACKED_FIELDS)
    return hashlib.sha256(text.encode()).hexdigest()


def _snapshot(listing, run, raw):
    ListingSnapshot.objects.create(
        listing=listing, run=run,
        asking_price=listing.asking_price, annual_revenue=listing.annual_revenue,
        annual_profit=listing.annual_profit, profit_margin=listing.profit_margin,
        is_active=listing.is_active, content_hash=listing.content_hash, raw=raw,
    )


def _record_changes(listing, run, old):
    for field in TRACKED_FIELDS:
        new = _s(getattr(listing, field))
        if old[field] == new:
            continue
        if field == "asking_price" and old[field] and new:
            if Decimal(new) < Decimal(old[field]):
                kind = ListingEvent.Type.PRICE_REDUCED
            else:
                kind = ListingEvent.Type.PRICE_INCREASED
        else:
            kind = ListingEvent.Type.DETAILS_CHANGED
        ListingEvent.objects.create(
            listing=listing, run=run, event_type=kind, field=field,
            old_value=old[field][:255], new_value=new[:255],
        )


def _store(source, run, std, now):
    new_hash = _hash(std)
    data = std.model_dump(exclude={"external_id", "raw"})
    with transaction.atomic():
        listing = SourceListing.objects.filter(
            source=source, external_id=std.external_id).first()
        if listing is None:
            listing = SourceListing.objects.create(
                source=source, external_id=std.external_id, first_seen_at=now,
                last_seen_at=now, content_hash=new_hash, raw=std.raw, **data,
            )
            _snapshot(listing, run, std.raw)
            ListingEvent.objects.create(
                listing=listing, run=run, event_type=ListingEvent.Type.LISTED)
            return "new"

        old = {f: _s(getattr(listing, f)) for f in TRACKED_FIELDS}
        was_inactive = not listing.is_active
        changed = listing.content_hash != new_hash
        for field, value in data.items():
            setattr(listing, field, value)
        listing.raw = std.raw
        listing.last_seen_at = now
        listing.missed_runs = 0
        listing.is_active = True
        listing.content_hash = new_hash
        listing.save()

        if was_inactive:
            ListingEvent.objects.create(
                listing=listing, run=run, event_type=ListingEvent.Type.RELISTED)
        if changed:
            _record_changes(listing, run, old)
        if changed or was_inactive:
            _snapshot(listing, run, std.raw)
        return "changed" if changed else "same"


def _mark_seen(source, raw, now):
    """A record that failed validation was still present, so it must not look missing."""
    record_id = raw.get("id") if isinstance(raw, dict) else None
    if record_id is not None:
        SourceListing.objects.filter(source=source, external_id=str(record_id)).update(
            last_seen_at=now, missed_runs=0)


def _remove_missing(source, run, now):
    stale = SourceListing.objects.filter(
        source=source, is_active=True, last_seen_at__lt=now)
    stale.update(missed_runs=F("missed_runs") + 1)
    removed = 0
    for listing in stale.filter(missed_runs__gte=REMOVE_AFTER_MISSED_RUNS):
        with transaction.atomic():
            listing.is_active = False
            listing.save(update_fields=["is_active"])
            _snapshot(listing, run, listing.raw)
            ListingEvent.objects.create(
                listing=listing, run=run, event_type=ListingEvent.Type.REMOVED)
        removed += 1
    return removed


def _alert(source, run):
    subject = f"[Listing Aggregator] {source.name} is {source.health}"
    body = (
        f"Run {run.pk} finished with status '{run.status}'.\n"
        f"Seen: {run.seen_count}, failed records: {run.failed_count}, complete: {run.complete}\n\n"
        f"{run.error_summary}"
    )
    logger.warning("%s\n%s", subject, body)

    if settings.ALERT_EMAILS:
        try:
            send_mail(subject, body, None, settings.ALERT_EMAILS)
        except Exception:  # an alert problem must never break a run
            logger.exception("Could not send the alert email")


def _update_health(source, run):
    previous = source.health
    source.last_run_at = run.finished_at
    if run.status == IngestionRun.Status.SUCCESS:
        source.consecutive_failures = 0
        source.last_success_at = run.finished_at
        source.health = Source.Health.HEALTHY
    else:
        source.consecutive_failures += 1
        source.health = (Source.Health.FAILING if source.consecutive_failures >= FAILING_AFTER
                         else Source.Health.WARNING)
    source.save(update_fields=[
                "last_run_at", "last_success_at", "consecutive_failures", "health"])
    if source.health != previous and source.health in (Source.Health.WARNING, Source.Health.FAILING):
        _alert(source, run)


def run_source(source, limit=None, heartbeat=None):
    """Run one source now. `limit` stops early (for testing): no removals, no health change."""
    run = IngestionRun.objects.create(source=source)
    now = run.started_at
    connector = get_connector(source)
    counts = {"new": 0, "changed": 0, "same": 0}
    seen = failed = 0
    errors = []
    crashed = stopped_early = False

    records = connector.fetch()
    try:
        for raw in records:
            if limit is not None and seen >= limit:
                stopped_early = True
                break
            seen += 1
            if heartbeat and seen % 100 == 0:
                heartbeat()
            try:
                std = connector.to_standard(raw)
                counts[_store(source, run, std, now)] += 1
            except Exception as exc:  # one bad record must not stop the run
                failed += 1
                if len(errors) < 5:
                    rid = raw.get("id") if isinstance(raw, dict) else "?"
                    errors.append(f"record {rid}: {exc}"[:300])
                _mark_seen(source, raw, now)
    except Exception as exc:
        crashed = True
        errors.append(f"Run stopped: {exc}"[:500])
        logger.exception("Run for %s stopped", source.slug)
    finally:
        records.close()

    complete = connector.complete and not crashed and not stopped_early and seen > 0
    removed = _remove_missing(source, run, now) if complete else 0

    if crashed:
        run.status = IngestionRun.Status.FAILED
    elif not complete or (seen and failed / seen > MAX_FAILED_SHARE):
        run.status = IngestionRun.Status.PARTIAL
    else:
        run.status = IngestionRun.Status.SUCCESS
    run.complete = complete
    run.expected_total = connector.expected_total
    run.seen_count = seen
    run.new_count = counts["new"]
    run.changed_count = counts["changed"]
    run.removed_count = removed
    run.failed_count = failed
    run.error_summary = "\n".join(errors)
    run.finished_at = timezone.now()
    run.save()

    if not stopped_early:
        _update_health(source, run)
    return run
