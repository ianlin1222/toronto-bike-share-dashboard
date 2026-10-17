# Accepted implementation plan and status

Accepted for implementation on 2026-09-07. This file is the durable status and
evidence ledger for the approved plan. A checked box means its acceptance evidence
exists; software completion never implies validated prediction performance.

## Product contract

- Recommend a primary and distinct alternative return station near a destination.
- Inputs are destination latitude/longitude, exact horizon 5/10/15/30 minutes
  (default 15), and radius 100–2,000 m (default 750 m).
- One common arrival horizon is applied to all candidates in version one.
- Distances are Haversine straight-line distance, not routed distance.
- Generic bicycle compatibility uses the publisher's total reported functional
  docks. Compatibility arrays are retained and the assumption is disclosed.
- Modes are `fixture_demo`, `live_baseline`, and `validated_model`. Forecast
  probabilities remain null until the live-history, leakage, calibration, policy,
  and untouched-test gates all pass.

## Non-negotiable evidence policy

The 82% recommendation-success and 14-percentage-point uplift values are targets,
not observations. Synthetic fixtures test software only. Headline results require
self-collected live history, a frozen replay protocol, and an untouched final test.
Every result must include numerator, denominator, coverage, abstentions, missing
outcomes, exclusions, date range, horizon, distance trade-off, and day-block
uncertainty interval.

## Architecture decisions

- Python 3.13, PostgreSQL 18.6, FastAPI, and Power BI are the core stack.
- One repository/database, one independent restartable collector, one API.
- Docker Compose is the primary local runtime; API/database bind to localhost.
- Raw response evidence is content-addressed with SHA-256; normalized observations
  preserve source, retrieval, ingestion, and station reporting timestamps.
- Metadata is type-2 history and is joined as it was known at each decision time.
- Reported dock availability is authoritative; null values never become zero.
- UTC stores/order events; `America/Toronto` derives calendar/DST features.
- No PostGIS, Kafka, Kubernetes, paid services, or public deployment in v1.
- Power BI uses Import mode and a view-only database role. Windows authoring is
  required before M6 may be complete.

## Milestone ledger

| Milestone | Status | Acceptance evidence / blocker | Next action |
|---|---|---|---|
| M0 contracts/bootstrap | Local runtime accepted | Docker engine 29.7.2, Compose 5.5.0, Python 3.13.15 container and PostgreSQL 18.6 run on this Mac; `make start` configures credentials and waits for live data | Keep a clean-checkout drill separately pending |
| M1 feed → PostgreSQL → station API | Vertical slice accepted | Retained PostgreSQL 18.6 database, 1,069-station GBFS batches, and real API-role recommendations work; migration 0004 fixes restricted-role idempotent writes | Continue collection |
| M2 reliable collection/coverage | Collecting; long-run acceptance pending | Restartable Compose collector began 2026-09-16 18:55:39 UTC; tests cover retries/quality/archive; 24-hour completeness/storage and automatic maintenance are not accepted | Keep host running; collect a 24-hour audit and implement maintenance scheduling |
| M3 features/labels/training | Components only; incomplete | Feature/label/split/model-selection tests and non-approvable fixture artifact pass; live extraction/training orchestration is still blocked in code | Implement live extraction/training without accessing future test outcomes |
| M4 frozen held-out replay | Blocked | Needs 84 qualifying live days, including untouched 14-day test | Do not access/fabricate final outcomes |
| M5 recommendation API/demo | Usable live baseline; forecast serving incomplete | Actual Docker-backed recommendations, station-name search, presets, desktop/mobile rendering and input/degraded states checked; validated inference is not wired | Preserve honest null probabilities; complete approved-model serving only with M3/M4 evidence |
| M6 Power BI | Support assets ready; artifact blocked | Views, role grants, DAX/theme/relationships/build checklist exist; actual PBIX/PBIP must be built and checked on Windows | Perform Windows authoring/refresh/visual verification |
| M7 delivery/acceptance | In progress | One-command startup, updated runbook and isolated logical backup/restore verified; clean checkout, full deployment recovery and Windows report remain | Complete remaining acceptance separately |

## Live-history readiness gates

- At least 84 qualifying calendar days: train 49, model-validation 7,
  calibration 7, policy-selection 7, untouched final test 14.
- Global timestamp boundaries with a 30-minute embargo and label-boundary purge.
- At least 95% successful scheduled polls overall and 90% on every included day.
- At least 98% accepted station records in included complete batches.
- At least 90% known future-label coverage in replay.
- At least 1,000 positive and 1,000 negative labels per horizon across validation
  and test, plus 200 evaluable scarcity requests for scarcity claims.
- No unresolved time, feature-schema, leakage, archive, or calibration failure.
- Forecast policy passes the predefined >=95% coverage and <=200 m median
  extra-distance validation constraints.

## Frozen evaluation outline

Examples are station × five-minute decision time × horizon. A label uses the first
canonical observation retrieved at/after arrival and within 90 seconds, provided
its station report is fresh. Missing or stale future observations are unknown.
Candidate and outcome rules are identical for all policies. The four comparisons
are nearest operational, nearest current dock, current buffer/distance, and
forecast/distance. Protocol inputs, seeds (`20260907`), model and policy hashes are
frozen before final-test access. Day-block bootstrap intervals use 2,000 resamples.

## Verification log

| Date (UTC) | Command/check | Result |
|---|---|---|
| 2026-09-07 | Initial workspace audit | Empty new project; no existing code/data/instructions |
| 2026-09-07 | `git init` | Initial sandbox attempt failed; approved elevated retry succeeded |
| 2026-09-07 | `brew install uv`; `uv lock`; `uv sync --group dev` | uv 0.12.10, CPython 3.13.15, 59 exact locked packages including pyarrow 23.0.1 |
| 2026-09-07 | Ruff and strict mypy | Passed for application, tests, migrations, and scripts |
| 2026-09-07 | `pytest tests/unit tests/contract tests/e2e` | 31 passed; two upstream TestClient deprecation warnings; no failures |
| 2026-09-07 | Disposable PostgreSQL 18.1 integration suite | Final suite: 6 passed; migration up/down, idempotency, quarantine, reporting, archive hashes/row reconciliation, and API/reporter raw-table denial passed |
| 2026-09-07 | Real GBFS v3 smoke ingestion to disposable PostgreSQL | Batch `40d6e250-8f21-57ee-affd-89445123380c`: 1,065/1,065 accepted, 0 quarantined, 100% record coverage; same-minute rerun was duplicate without refetch |
| 2026-09-07 | Live-backed API smoke | `/readyz`, station `7000`, and City Hall recommendation returned 200 after fixing one query typing defect; probabilities null and fallback explicit |
| 2026-09-07 | Partition-aware one-batch storage measurement | 1,065 snapshots occupied 888 kB in temporary PostgreSQL 18.1; not a 24-hour or 90-day projection |
| 2026-09-07 | Fixture training rerun | Stable run ID `6f1c3fab-7924-5bfb-8a6d-85d21bb2f6c2` and SHA `69b224e...cdb62`; non-approvable and not performance evidence |
| 2026-09-07 | Fixture API load: 1,000 requests, concurrency 25, seed 20260907 | 0 errors; p50 14.91 ms, p95 19.53 ms, max 67.12 ms; local fixture result only |
| 2026-09-07 | `uv build`; wheel content inspection | Reproducible sdist/wheel built; packaged demo HTML and deterministic fixture JSON both present |
| 2026-09-07 | `brew install --cask docker` | Downloaded Docker Desktop 4.89.0, then Homebrew rolled back because interactive administrator password was required |
| 2026-09-07 | Disposable database teardown | Both temporary PostgreSQL clusters and smoke data were stopped and permanently removed after evidence capture |
| 2026-09-16 | Docker/Compose startup | Engine 29.7.2 / Compose 5.5.0; fixed PostgreSQL 18 parent volume and initialization helper ordering; API 8080 / DB 55432 avoid unrelated existing services |
| 2026-09-16 | `make start`; `make smoke`; `make data-audit` | Live baseline ready; primary/alternative City Hall recommendation 200 with null forecasts; 11/11 successful polls, 11,759 snapshots, zero quarantine by 19:05 UTC; collection is retained |
| 2026-09-16 | Desktop/mobile browser checks | Real catalogue has 1,069 station locations; landmark/name inputs, sample empty-state expansion, live cards and invalid-name guidance checked; 390 px mobile has no horizontal overflow |
| 2026-09-16 | `make test`; `make lint` | 44 tests passed on isolated PostgreSQL 18.6, two upstream TestClient deprecation warnings; Ruff/strict mypy passed |
| 2026-09-16 | Real live-data load (1,000 requests, concurrency 25) | Initial p95 1,341.53 ms missed target; after bounded serving cache, p50 110.73 ms / p95 266.32 ms / max 558.76 ms, zero errors. Local acceptance only; see verification notes |
| 2026-09-16 | Controlled collector pause/restart | After 120-second freshness limit, readiness/recommendations returned 503; browser displayed paused updates/retry guidance. Restart restored live cards; collector left running. Intentional test gaps remain in retained history |
| 2026-09-16 | Logical backup/isolated restore | 16,035 snapshot rows and 34 raw-evidence hashes matched source counts/digests; revision 0005. Backup retained locally; temporary restore database removed. Full credential/ACL/offsite recovery remains outside this drill |

Update this table with exact commands, versions, hashes, observable results, and
unresolved blockers as implementation proceeds.

## Requirement traceability

| Capability | Implemented deliverables | Acceptance/evidence status |
|---|---|---|
| Live Python/PostgreSQL pipeline | GBFS v3 plus v2.3-compatible adapter, raw hashes/bodies, migrations, type-2 metadata, snapshots, collector, retries, events, summaries and archive | Real PostgreSQL 18.6 collection running from Sept 16; 24-hour coverage and maintenance scheduling pending |
| Temporal/spatial/utilization/rolling/nearby features | Shared schema/hash and point-in-time builder with DST, irregular windows, coverage flags and nearest-five neighbour rule | Unit/leakage tests pass; live ablations and value remain unmeasured |
| FastAPI primary/alternative ranking | Health/station/prediction/recommendation contracts, fixture/live fallback, request IDs, coarsened request persistence and responsive demo | Docker-backed API and browser baseline verified; approved-model inference/rollback and validated probabilities remain pending |
| Power BI reporting | Six original bounded reporting views plus the v0.2 dashboard observation view, aggregates, view-only role, DAX, theme, relationships and three-page specification | PostgreSQL view tests pass; PBIX/PBIP/Windows refresh and visual checks blocked; browser dashboard is separate |
| Reproducible nearest baseline | Four policy definitions, deterministic split/selection and paired day-block replay metric code | Software unit tests pass; frozen M4 replay and actual rates/uplift blocked on 84 qualifying days |
| 82% / +14 percentage points | No hard-coded claim or target-tuned acceptance | Unverified and not claimable; only M4 may populate actual results |

## Next executable action

Use `make start` (or `Start.command`) and open http://127.0.0.1:8080. Leave Docker
Desktop and the collector running; after 24 hours run `make data-audit` and
`make data-readiness` and record actual coverage/storage. A separate next development
batch must implement reliable scheduled maintenance and live model orchestration.
Do not activate a model, claim forecast validation or populate performance cards.

## Version 0.2 — manual dashboard (2026-10-14)

Requested extension: use the supplied video as a visual reference, combining its
overview/chart/drill-down patterns with this project, without animation. The Sites
skill's local-only workflow was used; no site was registered, uploaded or published.

- Home and `/dashboard`: responsive Dockside overview with four inspectable KPI
  cards, hourly trend, daily profile, geographic station bubbles, full-station
  ranking, weekday/hour heatmap, sortable/searchable station table and poll coverage.
- Manual date/station/day/hour filters, chart selection, data tables and CSV exports.
  All date boundaries are Toronto-local; observed timelines preserve UTC/DST bins.
- `/v1/dashboard`, migration 0006 and `dashboard_station_hours` preserve source
  separation and summed observation denominators. `make dashboard-backfill`
  summarizes existing retained evidence, never reconstructs missing observations.
- Default selection is the available history within 31 days. Missing hours remain
  blank, unknown ratios remain null, and substantial coverage gaps are prominent.
- Current conditions are explicitly measured at the last manual refresh, separate
  from historical filtering. Out-of-Toronto/missing coordinates are disclosed and
  omitted only from the plot; source observations remain in totals/tables.
- `/demo` remains the original return-station finder. Forecast validation, trip
  flows, rebalancing measurements and the Power BI artifact are still pending.
- Version and lock metadata are 0.2.0; no chart package or frontend framework added.
  Docker no longer recursively changes ownership of the large environment, and
  documentation edits no longer invalidate the dependency-copy layer.
- Launcher now checks at least 10 GB free before building (20 GB recommended) and
  times out unresponsive Docker diagnostics, with nondestructive recovery guidance.

Verification collected during this extension:

| Check | Actual evidence |
|---|---|
| Reference inspection | Played/searched key frames of the 48.7-second video: overview, chart/map/ranking and calculation drill-down; no reference metrics imported |
| Real historical aggregation | 71,131 station-hour rows summarized from retained snapshots; range Sep 16–Oct 14, with major gaps; not 29 continuous days |
| Live endpoint before disk-full incident | `/v1/dashboard` returned 200 in a single 231 ms spot check, 1,075 observed stations in the then-default week. This is not a load-test SLA |
| Real-data desktop check | 1,078 station IDs over the broader date selection; approximately 2.7% successful scheduled-poll coverage, explicitly shown. `(0,0)` coordinate distortion discovered and addressed |
| Database-inclusive tests before final plotting/launcher changes | 55 passed on isolated PostgreSQL 18.6; fixed an old fixture-clock bug that overflowed latency after the fixture aged past 24 days |
| Final non-database tests and static checks | 54 passed; Ruff, strict mypy (39 source files), and JavaScript syntax check passed; two upstream TestClient warnings |
| Browser interaction checks | Desktop and 390 px mobile (no page overflow), date/station/day/hour filtering, reset, invalid station, empty results, calculation inspector and CSV download; sample exports explicitly carry `source_kind=synthetic`, numeric negative longitude remains numeric |
| Environmental failure/recovery | Docker rebuild exhausted disk and made its filesystem read-only. No data/volumes were deleted. User freed space; normal restart timed out, so the verified hung Docker processes were terminated before recovery. Final deployment/retest recorded below when verified |

Final delivery acceptance (2026-10-14 16:14 UTC):

| Check | Verified result |
|---|---|
| Recovery and deployment | User freed disk space; normal Docker restart had hung, but terminating only its verified remaining processes allowed a clean restart and successful image build. Migration 0006, existing database, API and independent collector are running; no volume reset or data deletion |
| Final full suite | **62 passed**, two upstream TestClient warnings. Existing test image with current `src`, `tests`, `alembic` and `scripts` mounted read-only; disposable PostgreSQL 18.6 database. The live database was not reset |
| Static checks | Ruff, strict mypy (39 files), JavaScript syntax passed |
| Live smoke | `make smoke` returned healthy `live_baseline`, fresh complete poll at 16:14:01 UTC, real primary/alternative stations and null forecast probabilities |
| Final real-data UI | `/dashboard` loads the collected Sep 16–Oct 14 range, 1,077 mapped stations with one disclosed omission, temporal gaps and approximately 2.7% poll coverage; no browser JavaScript console errors |
| Screenshot | `var/dashboard-v0.2-live.jpg` contains the observed live dashboard, not synthetic results; ignored runtime evidence |
| Teardown | Temporary sample/preview servers and isolated test database stopped; live API/database/collector intentionally left running |

Dashboard software is accepted for this extension. Data/evaluation/Power BI
statuses above remain unchanged. Open http://127.0.0.1:8080/dashboard; use manual
filters and Refresh data. Keep Docker Desktop running and monitor free disk space.

## Analytical portfolio edition 1.0.0 (2026-10-17)

User-authorized extension: create professional SQL analysis, an Excel workbook
and a PDF case study from the collected real data, then commit and push to the
existing GitHub repository. Application version remains 0.2.0; no production
model, collector configuration or database schema was changed.

Deliverables:

- `analysis/portfolio/`: frozen contract, 11 SQL files, read-only exporter,
  aggregate CSV/JSON exports, manifests, findings and interview walkthrough.
- `outputs/portfolio-2026-10-17/Dockside_Analysis.xlsx`: seven sheets, eight native
  tables, two charts, station/day-type controls and formula-linked analysis.
- `output/pdf/Dockside_Case_Study.pdf`: five-page evidence-first case study.
- Artifact builders, independent saved-file checks, data reconciliation tests
  and PostgreSQL SQL-contract tests. CI now includes portfolio Python linting.

| Acceptance check | Evidence |
| --- | --- |
| Real source | Live snapshots retrieved and ingested before 2026-10-17 17:00 UTC; no synthetic observations or trip reconstruction |
| Frozen window | 2026-09-16 18:55 UTC inclusive to 2026-10-17 17:00 UTC exclusive; Toronto calendar |
| SQL execution | Repeatable-read read-only extraction; one shared materialized CTE scan; no production data mutation |
| Counts | 840,283 eligible unique reports, 790,386 with a dock (94.1%); 1,075 stations |
| Coverage | 1,503 successful / 44,525 expected minute slots (3.4%); 11 observed dates; 21 absent dates |
| Quality | Repeated source reports deduplicated; freshness and conflict sensitivity published; 198,740 future-report timestamp quarantines disclosed without an unproven cause |
| Reconciliation | Station/date/hour/station-date totals, aggregate hashes and SQL hashes pass |
| Full suite | 65 passed against isolated PostgreSQL 18.6; two upstream TestClient deprecation warnings; isolated test service stopped afterward |
| Static checks | Ruff including portfolio scripts, strict mypy (39 source files), JavaScript syntax and diff whitespace checks pass |
| Excel artifact | Recalculated; station, missing-ID and day-type controls tested; 3,473 cached formulas, no error cells; native chart/table/dropdown parts verified; all sheet previews reviewed |
| Excel application | Native Microsoft Excel did not respond; application-level opening/interaction remains unverified and is disclosed |
| PDF | Five pages rendered and visually inspected; extractable text, key numbers and delivered-file hash verified |
| Privacy | Only public station aggregates and metadata published; no rider requests, raw source bodies, credentials, database volumes or runtime symlinks |

The spreadsheet skill required native workbook authoring, recalculation and
preview checks. Native tables/formulas are delivered; no unsupported PivotTable
or slicer claim is made. The PDF skill required rendering and reviewing every page.

Evidence remains **exploratory**. The 94.1% observed report rate is not prediction
accuracy, rider success or time-weighted reliability. The 84-day readiness gate,
held-out replay, 82% / +14 pp claims and real Power BI artifact remain pending.
Next executable action: maintain collection continuity and investigate timestamp
quarantines/conflicts before widening the analytical claims. Git publication is
verified separately by the successful push and repository CI result.

## Notebook PDF revision (2026-10-17)

User requested the PDF use the cleaner output format of a Jupyter notebook.
Replaced the hand-designed ReportLab report with an actual executed notebook,
nbconvert classic HTML and a Chromium-generated six-page PDF at the same path.
The `.ipynb` is the editable source of truth and includes all ten executed code
cells, three matplotlib figure outputs, pandas tables and explanatory Markdown.
The PDF/HTML omit five boilerplate input cells while retaining every output.
The PDF skill's render-and-review workflow was used to inspect all six pages;
the final export has no orphan paragraphs or clipped charts/tables.

- Frozen source data, SQL, reported headline metrics and Excel bytes are unchanged.
- The hourly figure now separates weekdays/weekends. Blank cells are explicitly
  insufficient support, not zero availability. This is not new performance evidence.
- Added hash-locked optional notebook dependencies in an isolated ignored local
  environment; the running application's dependencies and services are untouched.
- The HTML has no scripts and works offline; PDF rendering blocks HTTP(S) requests
  and uses a separate temporary browser, not the user's profile.
- Validation: ten successful execution counts, zero notebook errors, three figure
  outputs, matching executed-code/data hashes, six rendered/inspected PDF pages,
  updated artifact verification manifest, 57 passing non-database tests, Ruff and
  strict mypy. Earlier 65-test database-inclusive evidence remains recorded above.
- Updated READMEs, findings and the report cover preview. The prior PDF remains
  recoverable from Git history. Data/model/Power BI readiness statuses are unchanged.

Rebuild with `python analysis/portfolio/build_report.py` in the documented optional
notebook environment, then run `python analysis/portfolio/verify_artifacts.py`.
