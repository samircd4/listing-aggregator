from datetime import timedelta

from django.utils import timezone

from ingestion import tasks
from ingestion.models import IngestionRun
from sources.models import Source


class FakeLock:
    def __init__(self, free):
        self.free = free
        self.released = False
        self.extended = 0

    def acquire(self, blocking=False):
        return self.free

    def locked(self):
        return not self.free

    def release(self):
        self.released = True

    def extend(self, seconds, replace_ttl=False):
        self.extended += 1


def test_dispatch_queues_only_due_enabled_sources(monkeypatch, db):
    queued = []
    monkeypatch.setattr(tasks.run_source_task, "delay", queued.append)
    monkeypatch.setattr(tasks, "_lock", lambda s: FakeLock(free=True))
    now = timezone.now()
    never = Source.objects.create(
        slug="a", name="A", enabled=True, run_every_minutes=60)
    due = Source.objects.create(
        slug="b", name="B", enabled=True, run_every_minutes=60,
        last_run_at=now - timedelta(minutes=61),
    )
    Source.objects.create(
        slug="c", name="C", enabled=True, run_every_minutes=60,
        last_run_at=now - timedelta(minutes=10),
    )
    Source.objects.create(slug="d", name="D", enabled=False)
    tasks.dispatch_due_sources()
    assert sorted(queued) == sorted([never.pk, due.pk])


def test_dispatch_skips_a_source_that_is_running(monkeypatch, db):
    queued = []
    monkeypatch.setattr(tasks.run_source_task, "delay", queued.append)
    monkeypatch.setattr(tasks, "_lock", lambda s: FakeLock(free=False))
    Source.objects.create(slug="a", name="A", enabled=True)
    tasks.dispatch_due_sources()
    assert queued == []


def test_task_skips_when_locked(monkeypatch, db):
    source = Source.objects.create(slug="e", name="E")
    lock = FakeLock(free=False)
    ran = []
    monkeypatch.setattr(tasks, "_lock", lambda s: lock)
    monkeypatch.setattr(tasks, "run_source", lambda src,
                        heartbeat=None: ran.append(src))
    tasks.run_source_task(source.pk)
    assert ran == [] and not lock.released


def test_task_runs_and_releases_lock(monkeypatch, db):
    source = Source.objects.create(slug="f", name="F")
    lock = FakeLock(free=True)
    ran = []
    monkeypatch.setattr(tasks, "_lock", lambda s: lock)
    monkeypatch.setattr(tasks, "run_source", lambda src,
                        heartbeat=None: ran.append(src))
    tasks.run_source_task(source.pk)
    assert len(ran) == 1 and lock.released


def test_interrupted_run_is_marked_failed(monkeypatch, db):
    source = Source.objects.create(slug="g", name="G")
    stale = IngestionRun.objects.create(source=source)  # still "running"
    monkeypatch.setattr(tasks, "_lock", lambda s: FakeLock(free=True))
    monkeypatch.setattr(tasks, "run_source", lambda src, heartbeat=None: None)
    tasks.run_source_task(source.pk)
    stale.refresh_from_db()
    assert stale.status == IngestionRun.Status.FAILED
    assert "Interrupted" in stale.error_summary


def test_heartbeat_extends_the_lock(monkeypatch, db):
    source = Source.objects.create(slug="h", name="H")
    lock = FakeLock(free=True)
    monkeypatch.setattr(tasks, "_lock", lambda s: lock)

    def fake_run(src, heartbeat):
        heartbeat()

    monkeypatch.setattr(tasks, "run_source", fake_run)
    tasks.run_source_task(source.pk)
    assert lock.extended == 1
