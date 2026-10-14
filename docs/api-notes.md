# CatchBuys API notes

Last updated: 2026-10-14. Based on the CatchBuys docs, 200 sampled listings, and manual checks against three source sites.

## 1. Basics

- Base URL: `https://catchbuys.com/api/v1`
- Auth: `Authorization: Bearer <token>`
- Free during the POC. No paid plans yet.
- Response format: JSON. Exception: `429` responses return an **HTML** page.

## 2. Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/listings` | Paginated list, with filters. Returns `data` (array) and `meta`. |
| `GET /api/v1/listings/{id}` | Same 21 fields as the list, plus `description`, `total_revenue`, `growth_30d`, `customers`, `first_listed_at`. **Sampled (3 listings): the five extra fields are null or truncated, see section 5a.** |

### List query parameters

| Parameter | Notes |
| --- | --- |
| `q` | Keyword in listing name |
| `source` | One upstream source slug |
| `sources[]` | Several upstream source slugs |
| `types[]` | `saas`, `ecom`, `site`, `agency`, `other` |
| `industries[]` | Exact industry match |
| `mrr_min`, `price_min`, `price_max`, `age_min`, `margin_min` | Numeric filters |
| `sort` | `mrr` (default), `price`, `multiple`, `margin`, `age`, `added` |
| `dir` | `desc` (default) or `asc` |
| `per_page` | 1–100, default 25 |
| `page` | 1-indexed, default 1 |

**Warning:** unknown parameters are ignored silently. `limit=5` returned 25 rows. Use `per_page`.

There is **no** "updated since" filter and no sort by `updated_at`. Every run is a full crawl.

Upstream source slugs: flippa, empireflippers, quietlight, trustmrr, dealslide, businessesforsale, websiteclosers, daltons, indiemaker, microns, acquirebase, investorsclub, latonas, dotmarket, bpifrance, nicheinvestor, moneynomad, fih, ecommercebrokers, appbusinessbrokers, sellerforce, acquisitionsdirect.

## 3. Pagination

- Response: `{ "data": [...], "meta": { total, page, per_page, last_page, has_more } }`
- On 2026-10-14: `total` = 25,657; with `per_page=100`, `last_page` = 257.
- A page past the end returns `200` with `data: []` and `has_more: false`.
- Stop condition: `has_more` is `false`.

### Sorting has ties

With `sort=added&dir=asc`, many rows share the same `created_at` (71 of the first 100 rows had one timestamp). There is no tie-breaker, so rows can be skipped or repeated across page boundaries.

Crawl rules:
1. Deduplicate by `id`.
2. A crawl is **complete** only when the number of unique ids equals `meta.total`.
3. If not, run a second pass with a different sort and merge the results.
4. Mark listings as missing/removed only after a **complete** crawl.

## 4. Rate limiting

- 60 requests per window, per token.
- Headers on every response: `x-ratelimit-limit`, `x-ratelimit-remaining`.
- Request 61 returned `429` with `retry-after: 30` and `x-ratelimit-reset` (Unix timestamp, about 30 seconds ahead).
- The `429` body is HTML. Check the status code **before** parsing JSON.
- Client plan: self-throttle to about 55 requests a minute, honor `retry-after`, and back off on `429`.
- A full list crawl (257 requests) takes about 5 minutes.

## 5. List fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | int | Stable. Use as the external id. |
| `source` | string | Upstream marketplace slug |
| `source_id` | string | ID on the upstream marketplace |
| `name` | string | Quality varies. Some are long marketing sentences. |
| `url` | string | Upstream listing page |
| `website` | string/null | Null in all sampled rows |
| `type` | string | `saas`, `ecom`, `site`, `agency`, `other` |
| `industry` | string | Comma-separated text |
| `language` | string | Seen: `en`, `fr` |
| `currency` | string | Seen: `USD`, `GBP`, `EUR` |
| `asking_price` | int/null | Whole currency units (not cents) |
| `monthly_revenue` | int/null | **Unreliable for some sources, see section 7** |
| `annual_revenue` | int/null | Same |
| `annual_profit` | int/null | Same. This is profit, **not SDE**. |
| `profit_margin` | float/null | Percent |
| `multiple` | float/null | **Do not trust. Meaning differs by source.** |
| `age_years` | int/null | |
| `monthly_traffic` | int/null | Null in most rows |
| `thumbnail_url` | string/null | |
| `created_at` | datetime | When CatchBuys first saw it, **not** the original listing date |
| `updated_at` | datetime | |

## 5a. Detail endpoint (sampled 2026-10-14)

Sampled listings 66219 (empireflippers), 45001 (dealslide), 65910 (quietlight).

- All list values are identical in the detail response, including the same Empire Flippers errors.
- `total_revenue`, `growth_30d`, `customers`, `first_listed_at`: **null in all three.**
- `description`: truncated to about 100 characters (ends with "..."), or is the same text as `name`.
- Conclusion: the detail endpoint adds nothing useful today. Stage 1 does **not** fetch details.
- `created_at` is **not** the original listing date. DealSlide's page shows listing 45001 as 231 days old (about 25 Feb 2026), while `created_at` is 2026-05-18.
- Revisit if CatchBuys starts filling `first_listed_at`. That would be a connector-only change.

## 6. Not provided by the list endpoint

- SDE and cash flow
- State, city or any location
- Listing status (active, under contract, sold)
- Original listing date (`first_listed_at` exists only in the detail endpoint, and was null in all 3 sampled listings)
- Broker or seller

Removal can only be inferred when a listing disappears from a complete crawl.

## 7. Data quality by upstream source

| Upstream source | Checked against | Finding | Handling |
| --- | --- | --- | --- |
| `empireflippers` | 2 listings (97241, 91594) | **12x inflated.** `monthly_revenue` holds trailing-12-month revenue. `annual_revenue` and `annual_profit` are 12x too high. `multiple` is price / inflated profit. Price and margin are correct. | Correct in the normalization step (below). |
| `quietlight` | 1 listing (18829636) | Revenue and income match the site. `multiple` is null where the site says N/A. Price often null. | Store as given. |
| `dealslide` | 1 listing (45001) | Price correct. Revenue rounded (65,300,000 vs 65,264,033). Profit missing though the site shows it. `multiple` is the **revenue** multiple. Re-lists other marketplaces. | Store as given. |
| all others | not checked | Unknown | Store as given, mark unverified. |

Note: `dotmarket` titles quote monthly revenue (for example 3,528 EUR and 31 kEUR) that does not match the API `monthly_revenue` (1,811 and 4,700). Unexplained.

### Empire Flippers correction

```
true_annual_revenue = api.monthly_revenue
true_monthly_revenue = api.monthly_revenue / 12
true_annual_profit  = api.annual_profit / 12
profit_margin       = unchanged
multiple            = recomputed (asking_price / true_annual_profit)
```

Check: listing 97241, API profit 25,864,812 / 12 = 2,155,401 (site: $2,155,401). Listing 91594, API profit 9,800,436 / 12 = 816,703 (site: $816,703).

### Multiples

Ignore the API `multiple`. Compute our own: `profit_multiple = asking_price / annual_profit`, `revenue_multiple = asking_price / annual_revenue`.

## 8. Duplicates inside CatchBuys

CatchBuys lists the same business more than once when one marketplace re-lists another. Example: `dealslide` id 45001 ("WebsiteClosers presents...") and `websiteclosers` id 57, both at $22,500,000. In the 200 sampled rows there are at least 3 likely pairs. 13 of 32 sampled DealSlide names mention WebsiteClosers.

Handling: store everything, keep a fingerprint for Phase 2 matching. Before public launch, decide whether to hide re-lister sources such as `dealslide`.

## 9. Planned crawl design

1. **List pass only:** `per_page=100&sort=added&dir=asc`, about 257 requests. Dedupe by `id`. Check completeness against `meta.total`.
2. No detail pass in Stage 1 (see section 5a).
3. Days on market: use our own `first_seen_at`. For listings that already existed on our first crawl, `created_at` is only an approximation ("since CatchBuys first saw it").
4. Raw data is stored with the listing (latest copy) and with each history snapshot, instead of archiving every page of every run. A full crawl is about 22 MB, so page archives would grow by roughly 90 MB a day at four runs a day.

## 10. Open items

- Ask CatchBuys whether `first_listed_at`, `total_revenue`, `growth_30d` and `customers` will be filled, and whether `description` will stop being truncated.
- Read the CatchBuys terms on storing, showing and indexing data. Record retention limits.
- Verify more upstream sources against their sites (websiteclosers, businessesforsale, indiemaker, daltons, dotmarket).
- Decide how to treat non-USD and non-English listings.
- Report the Empire Flippers 12x error to CatchBuys.
