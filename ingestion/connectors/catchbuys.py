import logging
import time
from collections import deque
from datetime import datetime
from decimal import Decimal

import httpx
from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field

from .base import BaseConnector, StandardListing
from .normalize import make_fingerprint, money, ratio

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5

# The API sorts with ties, so one crawl can skip rows at page boundaries.
# Each extra pass uses a different order and page size to fill the gaps.
PASSES = [
    {"sort": "added", "dir": "asc", "per_page": 100},
    {"sort": "added", "dir": "desc", "per_page": 97},
    {"sort": "price", "dir": "desc", "per_page": 89},
    {"sort": "mrr", "dir": "asc", "per_page": 83},
]

# Checked by hand against the upstream sites (see docs/api-notes.md)
CORRECTED = {"empireflippers"}
VERIFIED_AS_GIVEN = {"quietlight", "dealslide"}


class CatchBuysRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int
    source: str
    source_id: str | None = None
    name: str
    url: str | None = None
    listing_type: str | None = Field(default=None, alias="type")
    industry: str | None = None
    language: str | None = None
    currency: str | None = None
    asking_price: Decimal | None = None
    monthly_revenue: Decimal | None = None
    annual_revenue: Decimal | None = None
    annual_profit: Decimal | None = None
    profit_margin: Decimal | None = None
    age_years: int | None = None
    thumbnail_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CatchBuysConnector(BaseConnector):
    slug = "catchbuys"

    def __init__(self, source, base_url=None, token=None):
        super().__init__(source)
        self.base_url = (base_url or settings.CATCHBUYS_BASE_URL).rstrip("/")
        self.token = token or settings.CATCHBUYS_API_TOKEN
        self.max_per_minute = source.max_requests_per_minute
        self._sent = deque()

    # ---- fetching -------------------------------------------------------
    def fetch(self):
        self.complete = False
        seen = set()
        total = 0
        headers = {"Authorization": f"Bearer {self.token}"}
        with httpx.Client(headers=headers, timeout=30) as client:
            for number, pass_params in enumerate(PASSES, start=1):
                page = 1
                while True:
                    body = self._get(client, {**pass_params, "page": page})
                    meta = body["meta"]
                    total = meta["total"]
                    self.expected_total = total
                    for record in body["data"]:
                        record_id = record.get("id")
                        if record_id is not None:
                            if record_id in seen:
                                continue
                            seen.add(record_id)
                        yield record
                    if not meta.get("has_more") or not body["data"]:
                        break
                    page += 1
                logger.info("CatchBuys pass %s: %s of %s listings seen",
                            number, len(seen), total)
                if len(seen) >= total:
                    break
        self.complete = len(seen) >= total

    def _throttle(self):
        """Never send more than max_per_minute requests in any 60-second span."""
        while True:
            now = time.monotonic()
            while self._sent and now - self._sent[0] >= 60.0:
                self._sent.popleft()
            if len(self._sent) < self.max_per_minute:
                break
            time.sleep(60.0 - (now - self._sent[0]) + 0.05)
        self._sent.append(time.monotonic())

    def _get(self, client, params):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._throttle()
            try:
                response = client.get(
                    f"{self.base_url}/listings", params=params)
            except httpx.TransportError:
                if attempt == MAX_ATTEMPTS:
                    raise
                time.sleep(min(2**attempt, 30))
                continue
            if response.status_code == 429:  # body is HTML, so never parse it
                wait = response.headers.get("retry-after", "30")
                time.sleep((int(wait) if wait.isdigit() else 30) + 1)
                continue
            if response.status_code >= 500:
                if attempt == MAX_ATTEMPTS:
                    response.raise_for_status()
                time.sleep(min(2**attempt, 30))
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(
            "CatchBuys: still rate limited after several retries")

    # ---- mapping --------------------------------------------------------
    def to_standard(self, raw):
        rec = CatchBuysRecord.model_validate(raw)
        annual_revenue = rec.annual_revenue
        monthly_revenue = rec.monthly_revenue
        annual_profit = rec.annual_profit

        if rec.source in CORRECTED:
            # CatchBuys read Empire Flippers' trailing-12-month figures as monthly (x12).
            annual_revenue = rec.monthly_revenue
            monthly_revenue = None if annual_revenue is None else annual_revenue / 12
            annual_profit = None if rec.annual_profit is None else rec.annual_profit / 12
            quality = "corrected"
        elif rec.source in VERIFIED_AS_GIVEN:
            quality = "as_given"
        else:
            quality = "unverified"

        price = money(rec.asking_price)
        annual_revenue = money(annual_revenue)
        annual_profit = money(annual_profit)
        currency = rec.currency or ""
        listing_type = rec.listing_type or ""

        return StandardListing(
            external_id=str(rec.id),
            upstream_source=rec.source,
            upstream_id=rec.source_id or "",
            name=rec.name,
            url=rec.url or "",
            listing_type=listing_type,
            industry=rec.industry or "",
            language=rec.language or "",
            currency=currency,
            age_years=rec.age_years,
            thumbnail_url=rec.thumbnail_url or "",
            asking_price=price,
            annual_revenue=annual_revenue,
            monthly_revenue=money(monthly_revenue),
            annual_profit=annual_profit,
            profit_margin=rec.profit_margin,
            profit_multiple=ratio(price, annual_profit),
            revenue_multiple=ratio(price, annual_revenue),
            data_quality=quality,
            source_created_at=rec.created_at,
            source_updated_at=rec.updated_at,
            fingerprint=make_fingerprint(
                currency=currency, asking_price=price,
                annual_revenue=annual_revenue, listing_type=listing_type,
            ),
            raw=raw,
        )
