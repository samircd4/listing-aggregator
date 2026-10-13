# Stage 1 Architect Plan: Data Engine

Oct 13, 2026 · @Somir Chandra Dash

## Goal

Stage 1 delivers a working data engine on the CatchBuys API in 2–3 weeks. The plan works backward from the demo Aaron will see:

- Real CatchBuys listings in the clean, standard format.
- The change history of one listing.
- The update log showing the system running on schedule.

## Build order

The work runs in five steps over 2–3 weeks, starting with the API discovery that shapes everything after it.

1. **Days 1–2: Discover the CatchBuys API and check its rules.**
   - Pull real samples. Record how login works (Bearer token), how paging works, the rate limits, and which fields exist (asking price, SDE, revenue, status, dates).
   - Find out whether it can return only changed listings or whether everything must be re-fetched. This decides how the update job works.
   - Read its terms on storing and showing data. Save the sample responses as test data.
2. **Week 1: Foundation.**
   - Set up Django, PostgreSQL, Redis and Celery in Docker Compose, with tests and code checks from day one.
   - Build the data tables, the admin source list, and the base template every connector follows.
3. **Weeks 1–2: CatchBuys connector.**
   - Build an async client with retries, backoff and rate limiting, and save every raw response.
   - Convert the data to the standard format and store it. Running the same update twice must not create duplicates.
4. **Week 2: History, health and scheduling.**
   - Add change detection, the update log, failure alerts and the scheduled job.
5. **Weeks 2–3: Proof and demo.**
   - Run on real data, write the tests and documentation, and prepare the demo.

## Core tables

Six tables hold the sources, the runs, the raw data, the current listings and their full history.

| Table | What it holds |
| --- | --- |
| Source | The registry row: schedule, rate limits, rights notes, on/off switch and health. |
| IngestionRun | One row per run, with counts of new, changed, removed and failed listings. |
| RawPayload | What the source actually sent. |
| SourceListing | The current cleaned listing, plus first seen, last seen and a normalized fingerprint for Phase 2 duplicate matching. |
| ListingSnapshot | Append-only record of a listing's tracked fields each time something changes. |
| ListingEvent | Typed history events, such as price lowered or status changed. |

## Design decisions that protect the client

Five decisions keep the data trustworthy and the client's accounts safe.

- **Missing data stays empty.** If CatchBuys has no SDE or revenue for a listing, we store nothing and never guess.
- **Removals are cautious.** A listing is marked "removed" only after a complete, successful run misses it, never after a failed or partial one.
- **One bad record does not stop a run.** It is logged and counted, and the rest continue.
- **The token lives in environment settings, never in the code.** At handover, the account moves into Aaron's name.
- **Raw data size stays in check.** Store it compressed, and check the CatchBuys terms on how long we may keep it.

## Risks to plan for

Two risks matter most in Stage 1: showing history on real data, and the stability of a free proof-of-concept API.

- **Demoing history.** Real listings may not change in a few days. Start scheduled runs early so real changes accumulate. If none appear, replay an edited sample, clearly labeled as a test.
- **POC stability.** A free proof-of-concept API can change or become paid. The connector design keeps that contained.

## Definition of done

Stage 1 is done when the three demo items work as described: real listings in the standard format, one listing's change history, and the update log running on schedule. Aaron then has 3–5 business days to approve, and the $480 payment is due on approval.
