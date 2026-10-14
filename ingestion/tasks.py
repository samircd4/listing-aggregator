import logging
from datetime import timedelta

import redis
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from redis.exceptions import LockError

from sources.models import Source

from .models import IngestionRun
from .services import run_source

logger = logging.getLogger(__name__)

LOCK_SECONDS = 10 * 60  # the lock expires 10 minutes after the last sign of life


def _lock(source):
    client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    return client.lock(f"ingest-lock:{source.pk}", timeout=LOCK_SECONDS)


def is_running(source):
    return _lock(source).locked()


def _extend(lock):
    try:
        lock.extend(LOCK_SECONDS, replace_ttl=True)
    except LockError:
        logger.warning("Could not extend the run lock")


@shared_task(ignore_result=True)
def run_source_task(source_id):
    source = Source.objects.get(pk=source_id)
    lock = _lock(source)
    if not lock.acquire(blocking=False):
        logger.info(
            "Run for %s skipped: another run is in progress", source.slug)
        return
    try:
        # We hold the lock, so any run still marked "running" was interrupted.
        IngestionRun.objects.filter(source=source, status=IngestionRun.Status.RUNNING).update(
            status=IngestionRun.Status.FAILED,
            finished_at=timezone.now(),
            error_summary="Interrupted: the worker stopped during this run.",
        )
        run_source(source, heartbeat=lambda: _extend(lock))
    finally:
        try:
            lock.release()
        except LockError:
            logger.warning("Lock for %s had already expired", source.slug)


@shared_task(ignore_result=True)
def dispatch_due_sources():
    now = timezone.now()
    for source in Source.objects.filter(enabled=True):
        interval = timedelta(minutes=source.run_every_minutes)
        due = source.last_run_at is None or now - source.last_run_at >= interval
        if due and not is_running(source):
            run_source_task.delay(source.pk)  # type: ignore
