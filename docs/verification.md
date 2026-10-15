# Verification record — updated 2026-09-16

## Current local acceptance

- Docker engine 29.7.2 / Compose 5.5.0, Python 3.13.15 containers and PostgreSQL
  18.6 are running. `make start` builds, migrates and waits for live readiness.
- API: http://127.0.0.1:8080; database: localhost:55432. Pre-existing services on
  8000, 5432 and 5433 were left alone. All project ports remain loopback-only.
- Persistent collection began 2026-09-16 18:55:39 UTC. The 19:05 UTC audit showed
  11 successful batches, 11,759 snapshots, 1,069 stations and zero quarantines.
  These are early runtime observations, not 24-hour completeness evidence.
- Full `make test`: **44 passed**, including PostgreSQL 18.6 integration,
  migrations up/down, restricted API-role recommendation inserts, privacy grants,
  archival with retained recommendation provenance, and serving-cache time safety.
- `make lint`: Ruff passed; strict mypy passed for 37 application source files.
- `make smoke`: liveness/readiness/recommendation HTTP 200. Primary and distinct
  alternative carry reported current docks, real source timestamps, straight-line
  distance and null forecasts. Real snapshots and recommendations are retained.
- Browser checks: sample empty results/radius expansion, live City Hall results,
  1,069 searchable locations, invalid-name guidance, mobile 390 px with no horizontal
  overflow, desktop 1,280 px. No external map tiles or geolocation permission.
- Identical local live load scenario: seed 20260907, 1,000 requests, concurrency 25.
  Before the serving cache: 0 errors, p50 518.78 ms, p95 1,341.53 ms, max 3,453.62 ms.
  After: **0 errors, p50 110.73 ms, p95 266.32 ms, max 558.76 ms** (5.16 s total).
  The second run meets the 500 ms p95 target. Builds/test workloads were also active
  during the first run, so this is acceptance evidence, not a controlled benchmark
  of the cache's isolated effect. It is not production latency or uptime evidence.
- API serving reuses an immutable city snapshot for at most two seconds. Every
  request rechecks health and recalculates station age; earlier decision times
  bypass the cache. Historical stores default to no caching.
- Controlled collector pause: `/readyz` and recommendations returned 503 after
  complete-batch age exceeded 120 seconds. The actual browser replaced results
  with “Station updates paused”, a retry action and diagnostic guidance.
  After restarting the collector, the browser's retry action returned live primary
  and alternative cards again. The live collector remains running; the separate
  sample server and isolated test database service were stopped.
- Logical backup restored successfully to the isolated test PostgreSQL 18.6
  instance (no owner/ACL restore). All **16,035 snapshot rows** matched source row
  digests; all **34 raw-payload hashes** matched. Migration revision was 0005.
  Backup retained at ignored `var/backup-20260916.dump`, SHA-256
  `eebbff3a4c3986dde8d853393706f1c2f43a39e5a21d88a95ec25115bf4c2145`.
  This verifies logical data recovery; it does not verify encrypted/offsite backups
  or recreate deployment credentials and privileges automatically.

## Still not accepted

- 24-hour coverage/storage projection, seasonal coverage, automatic archive/request
  retention scheduling, clean-checkout replay and unattended laptop uptime.
- Live feature extraction/training/evaluation orchestration and approved-model
  serving remain incomplete in code. The 84-day data gate is an additional
  requirement, not the only blocker. No measured forecast success/uplift exists.
- No Windows-authored/refreshed/visually verified PBIX or PBIP report exists.
- No public deployment, paid services, external uptime or Power BI publication.

## Earlier checks — 2026-09-07

## Passed

- `uv lock --check`: 59 packages resolved under Python 3.13.15.
- `ruff check src tests alembic scripts`: passed.
- `mypy`: passed in strict mode for 37 source files at the recorded run.
- Non-database suite: 31 passed (unit, contract, and mocked collector E2E).
- Disposable PostgreSQL 18.1: migration upgrade/downgrade, schema, reporting views,
  fixture ingestion/idempotency, per-record quarantine, partial/out-of-order state,
  summary/readiness logic, and verified Parquet/raw archive release passed.
- Public GBFS v3 smoke: 1,065/1,065 station records accepted, zero quarantined,
  deterministic batch replay returned `duplicate: true` without another fetch.
- Live-backed HTTP smoke: readiness, station status, and destination recommendation
  returned 200; forecasts were null and the fallback was explicit.
- Fixture load: seed 20260907, 1,000 requests, concurrency 25, zero errors,
  p50 14.91 ms, p95 19.53 ms, max 67.12 ms.
- Fixture artifact rerun produced stable ID and SHA. It is marked fixture,
  uncalibrated, unapproved, and cannot be loaded by the approved-artifact loader.
- The source distribution and wheel built successfully with pinned build backends;
  the wheel contains the browser demo and packaged deterministic fixture data.

## Historical limitations on 2026-09-07 (not current runtime status)

- Docker Desktop/Compose images and PostgreSQL 18.6 were not run. The cask download
  reached installation but macOS required an interactive administrator password;
  Homebrew rolled back the app.
- The database-role migration and entrypoint role-creation script passed against a
  disposable PostgreSQL cluster; their target 18.6 Compose-backed acceptance still
  needs Docker Desktop.
- No continuously running collector or 24-hour storage/completeness audit exists.
- No live feature dataset, trained/calibrated model, frozen replay, recommendation
  success rate, uplift, or confidence interval exists.
- No Power BI report artifact has been authored or verified on Windows.
- No public deployment, external uptime, backup restore, or Power BI publication
  has been attempted or authorized.

The two temporary PostgreSQL clusters and their smoke database were stopped and
permanently deleted after the recorded checks. The public responses were not kept
as historical evidence.
# Portfolio publication checks — 2026-10-15

- Ruff: passed.
- Strict mypy: passed, 39 source files.
- Unit, API-contract and collector end-to-end tests: 54 passed, two upstream
  deprecation warnings. Command: `UV_CACHE_DIR=.uv-cache uv run --locked --no-sync pytest tests/unit tests/contract tests/e2e`.
- PostgreSQL integration tests were not rerun for this documentation/publication
  batch; historical verification below is distinct from these checks.
- Publishable files exclude `.env`, local caches, live observations and model
  binaries. A selected dashboard screenshot is intentionally included.
- GitHub Actions results remain unverified until the initial push runs CI.
