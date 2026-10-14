from decimal import Decimal

import pytest

from ingestion import services
from ingestion.connectors.base import BaseConnector, StandardListing
from listings.models import ListingEvent, ListingSnapshot, SourceListing
from sources.models import Source


class FakeConnector(BaseConnector):
    slug = "fake"

    def __init__(self, source):
        super().__init__(source)
        self.records = []
        self.finishes = True

    def fetch(self):
        yield from self.records
        self.complete = self.finishes

    def to_standard(self, raw):
        if raw.get("bad"):
            raise ValueError("unusable record")
        return StandardListing(
            external_id=str(raw["id"]),
            name=raw.get("name", "Listing"),
            asking_price=Decimal(
                str(raw["price"])) if "price" in raw else None,
            raw=raw,
        )


@pytest.fixture
def setup(monkeypatch, db):
    source = Source.objects.create(slug="fake", name="Fake")
    connector = FakeConnector(source)
    monkeypatch.setattr(services, "get_connector", lambda s: connector)
    return source, connector


def test_first_run_creates_listings(setup):
    source, connector = setup
    connector.records = [{"id": 1, "price": 100}, {"id": 2, "price": 200}]
    run = services.run_source(source)
    assert run.status == "success" and run.complete
    assert (run.new_count, run.changed_count) == (2, 0)
    assert SourceListing.objects.count() == 2
    assert ListingSnapshot.objects.count() == 2
    assert ListingEvent.objects.filter(event_type="listed").count() == 2


def test_same_data_twice_adds_no_history(setup):
    source, connector = setup
    connector.records = [{"id": 1, "price": 100}, {"id": 2, "price": 200}]
    services.run_source(source)
    run = services.run_source(source)
    assert (run.new_count, run.changed_count) == (0, 0)
    assert ListingSnapshot.objects.count() == 2
    assert ListingEvent.objects.count() == 2


def test_price_drop_is_recorded(setup):
    source, connector = setup
    connector.records = [{"id": 1, "price": 100}]
    services.run_source(source)
    connector.records = [{"id": 1, "price": 80}]
    run = services.run_source(source)
    assert run.changed_count == 1
    event = ListingEvent.objects.get(event_type="price_reduced")
    assert (event.old_value, event.new_value) == ("100.00", "80.00")
    assert ListingSnapshot.objects.count() == 2


def test_removal_needs_two_complete_runs(setup):
    source, connector = setup
    connector.records = [{"id": 1, "price": 100}, {"id": 2, "price": 200}]
    services.run_source(source)
    connector.records = [{"id": 1, "price": 100}]
    services.run_source(source)
    assert SourceListing.objects.get(external_id="2").is_active
    services.run_source(source)
    gone = SourceListing.objects.get(external_id="2")
    assert not gone.is_active
    assert ListingEvent.objects.filter(
        listing=gone, event_type="removed").count() == 1


def test_incomplete_run_removes_nothing(setup):
    source, connector = setup
    connector.records = [{"id": 1, "price": 100}, {"id": 2, "price": 200}]
    services.run_source(source)
    connector.records = [{"id": 1, "price": 100}]
    connector.finishes = False
    services.run_source(source)
    services.run_source(source)
    assert SourceListing.objects.filter(is_active=True).count() == 2


def test_bad_record_does_not_stop_the_run(setup):
    source, connector = setup
    connector.records = [{"id": 1, "price": 100}, {
        "id": 2, "bad": True}, {"id": 3, "price": 300}]
    run = services.run_source(source)
    assert run.failed_count == 1 and run.new_count == 2
    assert run.status == "partial"
