import hashlib
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def money(value):
    if value is None:
        return None
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def make_fingerprint(*, currency, asking_price, annual_revenue, listing_type):
    """Cheap blocking key for Phase 2 duplicate matching. Not proof of a duplicate."""
    if asking_price is None and annual_revenue is None:
        return ""
    price = "" if asking_price is None else str(int(asking_price))
    band = ""
    if annual_revenue is not None:
        band = str(int((annual_revenue / 100_000).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
    key = f"{currency}|{price}|{band}|{listing_type}"
    return hashlib.sha1(key.encode()).hexdigest()
