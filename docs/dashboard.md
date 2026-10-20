# Dockside dashboard — v0.2

## Open and use

Run `make start` or double-click `Start.command`. Open
http://127.0.0.1:8080/dashboard. Docker Desktop must be running. To upgrade an
existing database, run `make dashboard-backfill` once: it creates hourly statistics
from retained snapshots, without reconstructing unobserved history. Fresh
collection subsequently refreshes the current and previous two hours.

The opening range covers available history, capped at 31 Toronto-local calendar
days ending at the latest aggregated hour. Choose From/Through, Station, Days and
Time of day, then **Apply filters**. **Reset** returns to the opening range.
The introduction explains the return-dock problem and provides two paths:
**Find a return dock** for current options, or **Explore the observations** for
historical analysis. **Show all stations** clears a station focus while preserving
the selected dates, weekday/weekend and local hour.
**Refresh data** fetches again with the selected filters. There is no autoplay,
animation, automatic refresh or routing service. Street maps now require internet
access to OpenStreetMap tiles and the pinned Leaflet CDN; no API key is required.

| View | What it shows | Manual interaction |
|---|---|---|
| KPI cards | Weighted average docks, observed dock availability, station count and collection coverage | Click for definitions, calculation and counts |
| Average docks over time | Hourly average reported usable docks | Hover/focus for values; click a point or View data |
| Average docks by hour | Aggregated Toronto-local hourly pattern | Click a bar to filter that hour |
| Station street map | OpenStreetMap streets and landmarks, current-known coordinates; colour = availability; size = average docks | Pan/zoom; select a marker for details/location link, then use its filter button |
| Station ranking | Highest observed share of zero-dock reports | Choose minimum usable reports; inspect visible numerator/denominator; click a station to filter |
| Week/hour heatmap | Availability by weekday and local hour | Click a nonempty cell for its actual counts |
| Station table | Filtered station aggregates | Search, sort, paginate, focus a station or export CSV |
| Station distribution | Number of stations in each zero-dock-share band | Adjust the station-support minimum; inspect bins or their member stations |
| Average / full-share scatter | Whether a station's average hides zero-dock observations | Hover/focus for counts; select a dot to focus the dashboard |
| Weekday / weekend profile | Count-weighted dock availability for each local hour and day type | Inspect both groups at an hour; export all 48 cells including unsupported ones |
| Observation-quality breakdown | Four non-overlapping categories of recorded canonical observations | Inspect the definition and counts for each group |
| Data health | Successful scheduled polls / expected polls, including offline gaps | Click a day or View data; inspect source and refresh timestamps |

All charts have data tables as a nonvisual alternative. Keyboard users can use
Tab/Enter/Space on chart points and buttons. The narrow layout stacks panels;
wide tables and the heatmap scroll within their panels, not the whole page.

The current-report strip is separate from historical filters. Its numbers describe
the last manual refresh, not continuously updated availability. Date/day/hour
filters do not apply to that strip; station selection does. For return guidance,
open **Find a return dock** (`/demo`), which retains the original freshness rules.
After two minutes without a new response, current counts are replaced with a
refresh warning; this does not change historical charts or assert a collector
failure. The data inspector preserves numeric precision and explains that rates
are fractions from zero to one, while chart labels show percentages.

The ranking-only minimum defaults to 100 usable reports, with options for 500 or
all available reports. It affects only the eight-row ranking and its data inspector,
not other charts or the station-table CSV. Ties use support count (descending),
then station ID. A report count is not a count of independent days; this exploratory
control is separate from the frozen notebook's 100-report / five-date rule.

## Deeper analysis — what the average hides

Open **Deeper analysis** in the sidebar. The repeated context line shows the
applied dates, station, day/hour filters, source kind and system collection coverage.
The four new views are calculated from the existing response's integer counts;
they do not query raw history again, train a model, or modify PostgreSQL.

| Question / skill demonstrated | Calculation and reading guide | Boundary on interpretation |
| --- | --- | --- |
| Is pressure widespread? **Distribution and segmentation** | Compute each station's `full = dock_observations - available_observations`. Assign `100 × full / dock_observations` to 0–<10, 10–<25, 25–<50, 50–<75, or 75–100% bands. Bars count stations once, not observations. | Bands are descriptive, not validated risk thresholds. The sentence below the chart counts included stations with ≥25% observed full share; it is not a prediction. |
| Does an average hide poor outcomes? **Bivariate exploration** | X = `docks_sum / dock_observations`; Y = `100 × full / dock_observations`. Equal-size dots represent stations, with exact counts accessible. | No capacity adjustment, causal coefficient or independent-sample significance test. Higher averages do not guarantee a dock at arrival. |
| Do day types differ? **Weighted group comparison** | Group `heatmap` cells by `floor(heat_key / 24) < 5` and `heat_key % 24`. Rate = sum of available counts / sum of usable counts. Do not average day-level percentages. | Different stations/dates and collection coverage can explain differences. This is unadjusted, not a matched-station or causal analysis. |
| Which observations qualify? **Denominator reconciliation** | Available = A; usable zero-dock = U−A; fresh but not usable = F−U; not fresh/time unknown = N−F. Here N = recorded canonical observations, F = fresh, U = usable, A = available. Each bar uses N as denominator; the four counts sum to N. | Quarantined/noncanonical records and missing polls are outside N. Fresh-but-not-usable combines operational and missing-count exclusions; this aggregate cannot separate their causes. |

The **minimum usable observations per station** control (100 by default, 500 or
all sample sizes) affects distribution and scatter only. Excluded unknown/sparse
station counts are shown. No usable denominator means exclusion even with “All.”
It does not change the original ranking control, KPI cards, main station CSV,
weekday/weekend chart or quality breakdown.

Weekday/weekend points require at least 100 usable observations **per group/hour**.
Counts below the threshold remain in the inspector/CSV, with a null plotted rate
and an explicit support status. No observations is different from a supported 0%.
Missing points break lines. The Y axis remains 0–100%. If the main day filter is
weekday-only, no weekend comparison is fabricated; the UI explains how to restore
both groups. DST repeated hours are combined just as in the existing heatmap.
Observation thresholds do not establish independence or adequate calendar coverage.

All four views have **View data** and the existing CSV download. Exports retain
the main filters/source/time metadata and include support settings and
`analysis_version=descriptive_v1` for the full analytical tables. Distribution
exports also include included/excluded station counts. Raw rates remain fractions;
the chart renders percentages. The station scatter click changes the main station
filter; **Show all stations** removes it while keeping time filters.

Suggested interview sequence:

1. State the return-dock problem and the selected observation period/coverage.
2. Show the distribution to explain why a network average can conceal variation.
3. Inspect a scatter point and contrast its mean with its full-observation share.
4. Compare weekdays/weekends at one hour and show the weighted numerator/denominator.
5. Finish with the quality breakdown and collection coverage. Explain why repeated
   reports and missing days prevent rider-success or seasonal claims.

This extension leaves the frozen SQL/Excel/notebook findings unchanged. It is
exploratory dashboard analysis with a different, polling-observation denominator.

## What the numbers mean

`dashboard_station_hours` stores canonical observation counts and sums keyed by
station, UTC hour and source kind. Only `live` rows are read by the live dashboard.
The collector creates these rows alongside existing reporting summaries. The
explicit sample-mode server instead generates in-memory deterministic charts and
labels both its UI and exports as synthetic; it never writes them into live history.

- **Fresh observation:** source station report is between 30 seconds ahead and
  300 seconds behind retrieval, with ingestion no later than aggregate calculation.
- **Usable denominator:** fresh, installed, return-capable reports with a known
  reported dock count. Unknown counts and nonoperational stations are excluded
  from this denominator, not treated as available or zero.
- **Average docks:** sum of reported docks / usable denominator. Counts weight
  aggregation, not averages of hourly/station averages.
- **Dock available:** positive-dock observations / usable denominator. It is an
  observed inventory proportion, NOT a forecast, trip success rate or rider trial.
- **Full-station share:** one minus observed dock availability. Sparse stations
  can rank highly; their denominators must be inspected before drawing conclusions.
- **Collection coverage:** successful distinct scheduled slots / expected slots
  throughout the selected local dates/hours, using configured polling cadence.
  Missing polls remain in the denominator; the incomplete current slot is omitted.
  Station selection does not change this system-wide measure.

UTC uniquely identifies hours through daylight saving transitions. The local-hour
profile and heatmap combine a repeated autumn hour; the timeline keeps its two
UTC bins distinct. Missing hours are not interpolated. Null ratios render as a
dash, not zero. These are observation-weighted summaries, not continuous
time-weighted measurements: repeated reports, irregular polls and gaps limit
representativeness. Metadata on the plot is current-known, not historical location.
Stations outside the existing Toronto service envelope (43.45–43.95 latitude,
−79.80–−79.00 longitude), including a publisher's `(0, 0)` location, are excluded
from the geographic plot with an omission count. Their observations remain in the
totals and station table; plot filtering does not rewrite or erase source evidence.

The historical range describes available aggregates, not complete coverage. Only
retained snapshots can be summarized during an upgrade; archived-only rows are
not silently imported. Original hashes and raw evidence remain unchanged.

## API and storage

### Street-map update (2026-10-20)

Both the dashboard and `/demo` return finder use the shared `maps.js` component,
Leaflet 1.9.4 (CDN files pinned with integrity hashes), and OpenStreetMap raster
tiles. The finder marks destination/primary/alternative as D/P/A; coincident
locations share a badge. Distances remain straight-line, not routed distances.
Keyboard-accessible popups use text nodes for station content, not raw HTML.

The browser directly contacts unpkg.com and tile.openstreetmap.org. These services
receive the client's IP; tile URLs reveal the viewed geographic area. Exact
coordinates are in explicit external location links, followed only on user click.
Attribution stays visible, browser caching is respected, and no tile prefetch,
offline download, API key or paid account is introduced. Tile service is best-effort:
load errors/timeouts display a warning; a missing map library falls back to a list
of coordinates and external location links. Data tables remain available.
Before a high-traffic public deployment, review provider capacity/terms and choose
a suitable tile service. Sources checked 2026-10-20:
[Leaflet quick start](https://leafletjs.com/examples/quick-start/) and
[OSM tile policy](https://operations.osmfoundation.org/policies/tiles/).

For an existing Docker install, rebuild only the API to serve the changed assets:
`docker compose up -d --build --no-deps api`, then reload the browser. Do not reset
the database or delete volumes.

Verification on 2026-10-20: 54 Python unit/contract tests and three shared-map
Node tests passed (`node --test tests/unit/maps.test.cjs`). Browser fixture checks
verified street tiles, marker popups, station filtering and coincident D/P finder
markers at a narrow viewport. These are UI checks, not availability evidence.
The Mac had about 5.2 GiB free, below the existing build threshold, so the seven
changed static assets were copied into the running API container instead of
rebuilding its image. Source changes are retained, but that container-only update
does not survive recreation from the old image: rebuild after freeing disk space.
The collector and database were not restarted or changed by this update.

`GET /v1/dashboard` accepts optional `start_date`, `end_date` (`YYYY-MM-DD`),
`station_id`, `day_type=all|weekday|weekend`, and `hour=0..23`. Dates are inclusive
in America/Toronto, limited to 31 days. Response contains `version`, `mode`,
`source_kind`, `generated_at`, `filters`, `coverage`, `summary`, `current`,
`stations`, `timeline`, `hourly`, `heatmap`, `health`, and `methodology`.

Invalid filters return 422, unknown station 404, unavailable database 503 with a
sanitized explanation. An empty selection returns 200 with empty charts and null
ratios. Historical charts can remain available when current ingestion is stale;
the strip then says the live feed is paused. A failed refresh labels retained
charts as the previous result instead of silently switching to samples.

Migration `0006_dashboard_hours` creates the aggregate table and a read-only
`reporting.v_dashboard_station_hours` view. The API cannot modify it; the reporter
can only select the view. It is an optional seventh view for Power BI, alongside
the original six report views. No rider coordinates enter this dashboard/export.
CSV exports include source kind, filter dates, day/hour selection and generated
timestamp. String formula prefixes are escaped; negative numeric coordinates stay
numeric. Exported data is not a saved forecast result.

## Design reference and scope

[Claude Turned Bike Data Into a Video](https://www.youtube.com/shorts/NPsdtMxg5wQ)
by Tech_D_coded, visually inspected on 2026-10-14, informed the overview KPI row,
time-series/hourly charts, station geography, rankings and click-through number
inspection. The reference's animation/export-video, trip flows, uphill/downhill
analysis and rebalancing counts are deliberately not reproduced. This project's
GBFS snapshots cannot substantiate those measures. No reference-video number is
used as project data.

The dashboard is local FastAPI-served HTML/CSS/JavaScript, with no frontend build
framework. Leaflet is a pinned browser dependency; street tiles are an external
service. Power BI authoring, live model orchestration and
held-out forecast evidence remain separately pending, as recorded in `PLANS.md`.

## Verification and maintenance

`make test` runs fixture/unit/API and disposable PostgreSQL integration tests,
including null denominators, weighted aggregation, DST date bounds, filters,
default range limits, provenance isolation, SQL permissions and idempotency.
Browser checks cover desktop/mobile, filters, chart inspection, CSV download,
empty results and the original finder. Synthetic-mode checks are not live evidence.
`make test-ui` runs fourteen dependency-free Node tests for ranking, historical
station selection, precision, elapsed-time warnings, map rendering/failure handling,
analytical bin boundaries, count-weighted day types and quality reconciliation.
See the [October maintenance review](usability-review.md#portfolio-maintenance--2026-10-20)
for the latest verification and remaining operating limitations.

For local operation use `make status`, `make logs`, `make doctor`, and `make stop`.
Watch free disk space: one-minute historical collection grows even while the UI is
closed. No automatic host-disk cleanup or maintenance scheduler is promised.

### Analytical extension verification (2026-10-20)

- 69 Python tests passed using the cached tool image, current read-only source mounts
  and disposable PostgreSQL 18.6; 14 Node tests passed. No schema migration or new
  library was needed. The two existing upstream TestClient deprecation warnings remain.
- Fixture browser checks covered inspectors, CSV download, weekday-only selection,
  low-support selections and 390 px / 1440 px layouts. The mobile document remained
  390 px wide; wide axes scroll within their chart panels. Synthetic exports are labeled.
- A real `/v1/dashboard` response reconciled: day-type usable counts equal the
  summary denominator; the four quality groups equal the recorded total; band
  station counts equal the included-station count. This is a runtime calculation
  check, not a new frozen case study or an independent performance result.
- One live browser fetch failed while local verification was running; the error
  state appeared and a manual refresh recovered. Its cause was not established.
  Liveness/readiness checks were healthy; this check does not substantiate uptime.
- Live screenshots: [station distribution / scatter](images/deeper-analysis-2026-10-20.png)
  and [day types / observation quality](images/analysis-quality-2026-10-20.png).
  These use September 20–October 20, 2026, all stations/days/hours and a station
  minimum of 100. They are not the frozen notebook window. Keyboard scatter
  drill-down, single-station support and return to all stations were checked.
- Updated static assets are served by the running local API. Disk space was about
  6 GiB, so the prior container-copy approach was retained. Free sufficient disk and
  run `make start` to rebuild the images before recreating containers. The collector
  and live database were not restarted; the disposable test service was stopped.

Sites skill guidance informed the question-led progression, explanatory captions
and responsive checks. This remains the existing local FastAPI application; no
hosted Site, paid chart service or new external data source was introduced.
