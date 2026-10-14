# Listing Aggregator

A modular platform that collects business-for-sale listings from many sources, standardizes them into one format, and records every change from the first day. It is the data engine behind a buyer lead-generation site for a business brokerage.

**Status:** Phase 1, Stage 1 (Data Engine). The CatchBuys API connector, data models, history tracking and ingestion runner are built. Scheduling, the public API and the website come in later stages.

## What it does

- Pulls listings from a source (CatchBuys first) through a **connector**.
- Cleans them into one **standard format** (prices, revenue, profit, industry, currency).
- Stores each listing once, and writes a **history snapshot and event** whenever something changes (price reduced, price increased, details changed, removed, relisted).
- Marks a listing as removed only after **two complete runs** miss it. A failed or partial run never removes anything.
- Logs every run and tracks each source's **health**, with alerts when a source gets worse.

## Tech stack

Python 3.12, Django 6.1, PostgreSQL 16, Celery with Redis, httpx, pydantic, pytest. Everything runs in Docker Compose. Packages are managed with [uv](https://docs.astral.sh/uv/).

## Project layout

```
config/          Django settings and the Celery app
sources/         Source registry: schedule, rights notes, health
ingestion/       Run log, runner (services.py), connectors, management commands
  connectors/    base.py (the contract), catchbuys.py, normalize.py
listings/        Listings, history snapshots, events
scripts/         API exploration helpers
tests/           Tests and fixtures (tests/fixtures/catchbuys/sample_records.json)
docs/            api-notes.md (what the CatchBuys API really returns)
```

## Quick start

Requires Docker Desktop and uv.

```powershell
# 1. Create your settings file and fill in the values
Copy-Item .env.example .env

# 2. Start everything (database, Redis, web, worker, beat)
docker compose up --build -d

# 3. Create the tables and an admin user
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
```

Open http://localhost:8000/admin. Add a **Source** with slug `catchbuys`, name `CatchBuys`, kind `API`. Leave `enabled` off until you are ready to schedule it.

### Settings (`.env`)

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django secret. Use a long random value. |
| `DEBUG` | `true` or `false` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Database login |
| `POSTGRES_HOST`, `POSTGRES_PORT` | `db` and `5432` inside Docker |
| `REDIS_URL` | `redis://redis:6379/0` inside Docker |
| `CATCHBUYS_BASE_URL` | `https://catchbuys.com/api/v1` (no trailing slash) |
| `CATCHBUYS_API_TOKEN` | Your CatchBuys Bearer token |
| `ALERT_EMAILS` | Comma-separated addresses for source health alerts |

Never commit `.env`. Only `.env.example` belongs in git.

## Common commands

```powershell
# Run tests (they need the database, so run them in Docker)
docker compose run --rm web pytest

# Run a source now, even while it is disabled
docker compose run --rm web python manage.py run_source catchbuys
docker compose run --rm web python manage.py run_source catchbuys --limit 100   # quick test

# Logs
docker compose logs worker --tail 50

# Reset the database (deletes all data)
docker compose down -v
```

## How the pipeline works

```
Source (API) -> Connector -> standard format -> runner -> listings + history + run log
```

1. The **connector** fetches records and maps each one to the standard format. It never touches the database.
2. The **runner** (`ingestion/services.py`) stores the listing, writes snapshots and events, handles removals, logs the run and updates the source's health.
3. A crawl counts as **complete** only if every record was read. Removals happen only after complete crawls.

## Adding a new source

1. Create `ingestion/connectors/<name>.py` with a class that extends `BaseConnector`. Implement `fetch()` (yield raw records) and `to_standard()` (map one record to `StandardListing`).
2. Add the class to the tuple in `ingestion/connectors/__init__.py`.
3. In the admin, add a Source whose `slug` matches the connector's `slug`. Fill in its rights notes, test it with `run_source <slug> --limit 50`, then enable it.
4. Add a test using a small saved sample of the source's data.

## Data notes (CatchBuys)

Read `docs/api-notes.md` before changing the connector. The main points:

- The API has no "updated since" filter, so every run is a full crawl (about 257 requests, 5 minutes).
- The rate limit is 60 requests a minute. The client throttles itself and obeys `Retry-After`. The `429` body is HTML, not JSON.
- **Empire Flippers figures are 12x too high** in CatchBuys. The connector corrects them. The API's own `multiple` is ignored, and multiples are computed from the corrected values.
- No location, SDE, status or true listing date is provided. `created_at` is when CatchBuys first saw the listing.
- CatchBuys contains some duplicates (one marketplace re-listing another). Matching and merging is planned for Phase 2. A fingerprint is already stored for it.

## Roadmap

- **Stage 1 (current):** connector framework, CatchBuys connector, history, runner, then scheduling and a "Run now" admin action.
- **Stage 2:** REST API, buyer registration and login, buyer activity tracking.
- **Stage 3:** Next.js website, deployment, one additional source.
- **Phase 2:** duplicate matching, saved searches, alerts, buyer profiles.
- **Phase 3:** state-by-state broker sources, analytics and market reports.
