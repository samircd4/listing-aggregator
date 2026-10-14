import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import respx

from ingestion.connectors.catchbuys import CatchBuysConnector

FIXTURE = Path(__file__).parent / "fixtures" / "catchbuys" / "sample_records.json"


BASE = "https://catchbuys.test/api/v1"


@pytest.fixture
def connector():
    source = SimpleNamespace(max_requests_per_minute=1000)
    return CatchBuysConnector(source, base_url=BASE, token="test")


@pytest.fixture
def records():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))["data"]
    return {r["id"]: r for r in data}


def page(ids, page_no, has_more, total):
    return {
        "data": [{"id": i} for i in ids],
        "meta": {"total": total, "page": page_no, "per_page": 100, "last_page": 2, "has_more": has_more},
    }


def test_empire_flippers_is_corrected(connector, records):
    one = connector.to_standard(records[66219])
    assert one.data_quality == "corrected"
    assert one.asking_price == Decimal("8700000.00")
    assert one.annual_revenue == Decimal("11099730.00")
    assert one.annual_profit == Decimal("2155401.00")
    assert one.profit_multiple == Decimal("4.04")

    two = connector.to_standard(records[50441])
    assert two.annual_profit == Decimal("816703.00")
    assert two.profit_multiple == Decimal("2.69")


def test_quietlight_is_kept_as_given(connector, records):
    listing = connector.to_standard(records[65910])
    assert listing.data_quality == "as_given"
    assert listing.asking_price is None
    assert listing.annual_profit == Decimal("10843118.00")
    assert listing.profit_multiple is None


def test_dealslide_has_revenue_multiple_only(connector, records):
    listing = connector.to_standard(records[45001])
    assert listing.annual_profit is None
    assert listing.profit_multiple is None
    assert listing.revenue_multiple == Decimal("0.34")


@respx.mock
def test_fetch_reads_all_pages_and_skips_repeats(connector):
    route = respx.get(f"{BASE}/listings").mock(side_effect=[
        httpx.Response(200, json=page([1, 2], 1, True, 3)),
        httpx.Response(200, json=page([2, 3], 2, False, 3)),
    ])
    assert [r["id"] for r in connector.fetch()] == [1, 2, 3]
    assert connector.complete is True
    assert route.call_count == 2


@respx.mock
def test_crawl_with_missing_rows_is_not_complete(connector):
    respx.get(f"{BASE}/listings").mock(side_effect=[
        httpx.Response(200, json=page([1, 2], 1, False, 3)),
    ])
    list(connector.fetch())
    assert connector.complete is False


@respx.mock
def test_429_waits_and_retries(connector, monkeypatch):
    sleeps = []
    monkeypatch.setattr("ingestion.connectors.catchbuys.time.sleep", sleeps.append)
    respx.get(f"{BASE}/listings").mock(side_effect=[
        httpx.Response(429, headers={"retry-after": "30"}, text="<html>Too Many Requests</html>"),
        httpx.Response(200, json=page([1], 1, False, 1)),
    ])
    assert [r["id"] for r in connector.fetch()] == [1]
    assert sleeps == [31]