# Usability and runtime reassessment — 2026-09-16

The earlier version was not ready for a first-time user. Its instructions assumed
working Docker commands and unused ports, the page required coordinates, and tests
had not exercised real recommendations under the API's restricted database role.

| User-visible problem | Resolution |
|---|---|
| `docker compose` missing despite Docker Desktop installation | Launcher detects the bundled Compose binary and opens Docker Desktop if necessary |
| Copy/edit passwords and repeat them in four URLs | `make start` creates local credentials, preserves custom values and restricts `.env` permissions |
| Port 8000 and PostgreSQL ports occupied by other applications | Defaults are 8080 / 55432; preflight diagnoses conflicts without stopping unrelated services |
| PostgreSQL 18 volume and helper-script initialization failures | Correct PostgreSQL 18 parent volume; helper SQL no longer auto-executes without its parameters |
| Fresh station reads worked but recommendations failed | Migration 0004 grants only conflict-key SELECT columns needed by idempotent INSERT; private-coordinate reads remain denied |
| Empty root URL and coordinates-only interface | Home page, landmark presets, searchable station catalogue, optional exact coordinates |
| Unclear sample/current/prediction distinction | Persistent health/mode explanations, current dock labels, null forecasts, ETA limitation beside the input |
| Loading/errors/no results gave no next action | Bounded requests, disabled repeat submission, retry button, expand-radius action, stale-result message |
| Dynamic source names interpolated into HTML | Render source data with text nodes; no raw feed strings interpreted as markup |
| Old complete feed hidden by a recent partial poll | Readiness and recommendations share complete-batch freshness requirements |
| Full snapshot history scanned on each request | Indexed per-station latest-observation query and metadata known at decision time; a two-second serving cache with time-travel protection |
| Tests could use live role names and remove them | Separate test-db service; cleanup only removes roles created by the test itself |
| Archival blocked by recommendation foreign keys | Migration 0005 retains provenance IDs/time after rows move to verified Parquet; mismatch rolls back deletion |

Browser checks exercised sample recommendations, Union Station empty results,
expansion to 2 km, and the live City Hall request. The mobile viewport at 390 px
showed no horizontal overflow. Live station catalogue returned 1,069 locations;
these observations are runtime checks, not prediction-performance measurements.

Acceptance checks: 44 tests passed, real live-data load p95 266 ms with zero errors
across 1,000 requests, stale-feed rejection observed in the browser, and a logical
backup restored into a disposable database with matching snapshot/raw hash digests.

Remaining work is explicit: live model training/extraction/replay and approved-model
serving are incomplete; the 84-day evidence requirement also remains. Power BI
needs a real Windows-built report. Automatic archival/request-retention scheduling,
full credential/ACL recovery, offsite backups, overnight laptop uptime and 24-hour
coverage have not been accepted. The app is usable as a local current-availability
recommender.
