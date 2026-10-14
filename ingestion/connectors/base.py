from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StandardListing(BaseModel):
    external_id: str
    upstream_source: str = ""
    upstream_id: str = ""
    name: str
    url: str = ""
    listing_type: str = ""
    industry: str = ""
    language: str = ""
    currency: str = ""
    age_years: int | None = None
    thumbnail_url: str = ""
    asking_price: Decimal | None = None
    annual_revenue: Decimal | None = None
    monthly_revenue: Decimal | None = None
    annual_profit: Decimal | None = None
    profit_margin: Decimal | None = None
    profit_multiple: Decimal | None = None
    revenue_multiple: Decimal | None = None
    data_quality: str = "as_given"  # as_given / corrected / unverified
    source_created_at: datetime | None = None
    source_updated_at: datetime | None = None
    fingerprint: str = ""
    raw: dict = Field(default_factory=dict)


class BaseConnector(ABC):
    slug: str

    def __init__(self, source):
        self.source = source
        self.expected_total: int | None = None
        self.complete: bool = False

    @abstractmethod
    def fetch(self) -> Iterator[dict]:
        """Yield raw records. When finished, set expected_total and complete."""

    @abstractmethod
    def to_standard(self, raw: dict) -> StandardListing:
        """Validate and map one raw record. Raise ValueError if it is unusable."""
