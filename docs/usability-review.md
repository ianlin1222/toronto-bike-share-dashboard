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

## Portfolio maintenance — 2026-10-20

Checkpoint `02b6d73` preserves the street-map and analyst README version before
this maintenance pass. The review covered dashboard/finder behavior, analytical
wording, responsive layout, startup safeguards, tests and publication hygiene.
It is a scoped review, not proof that every production risk is resolved.

| Finding | Fix and rationale |
| --- | --- |
| The page started with metrics before explaining the user problem | Added a problem-first introduction, current-dock and analysis paths, plus direct links to the executed notebook and source |
| Inspector rounded all numbers to one decimal, obscuring fractions and coordinates | Preserve raw numeric precision; explain fractions versus percentages and missing values |
| Ranking and its data table had different tie-breaks | One tested deterministic rule for both, with support count and station ID tie-breaks |
| Sparse stations could dominate a ranking without visible support | Added a ranking-only 100/500/all minimum and full/usable counts; counts are explicitly not independent samples |
| Historical stations absent from the current catalogue could not be focused | Resolve IDs against the historical result as well as the current catalogue |
| Getting back from a station focus required resetting unrelated filters | Added “Show all stations,” preserving the time selection |
| A current strip could retain live-looking numbers indefinitely | Replace current counts with a refresh warning after two minutes; keep historical evidence unchanged |
| A map initialization exception could interrupt the rest of rendering | Catch the failure and provide coordinate links and station actions; no silent blank map |
| Finder wording implied an arrival assessment in baseline mode | Explain that changing ETA does not change current-availability ranking and the alternative is not a later-arrival prediction |
| Coordinate privacy wording implied only local handling | Disclose rounded live-request retention and the external map services' viewed-area exposure |
| Frontend behavior was not exercised in CI | Added `make test-ui`, eight Node tests and a CI frontend step; API tests check the new assets and copy |

Design follows the existing warm green palette, with an editorial serif headline,
more readable labels, restrained dividers, improved spacing and mobile wrapping.
It adds no animation, fabricated testimonials, performance claims or new service.
The Sites skill's local-repository route guided purpose-first hierarchy and
responsive visual checks; no Site hosting was created.

Verification:

- 68 Python tests passed against isolated PostgreSQL 18.6, including migrations,
  idempotency, restricted roles, archive reconciliation, portfolio SQL, feature
  leakage and API contracts. Two upstream TestClient deprecation warnings remain.
- 59 non-database tests passed locally; eight Node frontend tests passed.
- Ruff, strict mypy (39 source files) and Git whitespace checks passed.
- Fixture browser checks covered 390 px and 1440 px viewports, recommendations,
  street maps/location links, ranking minimum, station focus/reset and precise
  inspector values. These are software checks, not real-world performance.
- Live browser checks on port 8080 confirmed the new homepage, real-history
  warning, street tiles and 1,076 mapped stations. Homepage and station-explorer
  screenshots are in `docs/images/`; no browser console errors were recorded
  during this check. These are runtime observations, not frozen study metrics.
- A cached test image initially contained an older launcher; mounting the current
  scripts/migrations alongside source and tests resolved that test-harness mismatch.
  The successful run tested current repository code, without rebuilding an image.

Operating limitations remain explicit: forecasting/model activation and a verified
Windows Power BI artifact are pending. Collection gaps and data-quality limitations
in the frozen study have not been erased. No new performance result was generated.
Automatic retention scheduling, offsite recovery and public hosting are not claimed.

Disk availability was approximately 5–7 GiB during this session, below the existing
10 GiB startup/build safety threshold. The eight changed static assets were copied
into the running API container; no production database or collector restart was
needed. **This updates the current container, not its cached image.** After freeing
enough disk space, run `make start` to build the committed version into the images.
Do not delete the PostgreSQL volume. Test database shutdown is separate from live
services. Secrets, raw data and rider request logs are excluded from the commit.
