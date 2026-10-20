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
**Refresh data** fetches again with the selected filters. There is no autoplay,
animation, automatic refresh or routing service. Street maps now require internet
access to OpenStreetMap tiles and the pinned Leaflet CDN; no API key is required.

| View | What it shows | Manual interaction |
|---|---|---|
| KPI cards | Weighted average docks, observed dock availability, station count and collection coverage | Click for definitions, calculation and counts |
| Dock availability trend | Hourly average reported usable docks | Hover/focus for values; click a point or View data |
| Availability by hour | Aggregated Toronto-local hourly pattern | Click a bar to filter that hour |
| Station street map | OpenStreetMap streets and landmarks, current-known coordinates; colour = availability; size = average docks | Pan/zoom; select a marker for details/location link, then use its filter button |
| Station ranking | Highest observed share of zero-dock reports | Click a station to filter; sample counts available in View data |
| Week/hour heatmap | Availability by weekday and local hour | Click a nonempty cell for its actual counts |
| Station table | Filtered station aggregates | Search, sort, paginate, focus a station or export CSV |
| Data health | Successful scheduled polls / expected polls, including offline gaps | Click a day or View data; inspect source and refresh timestamps |

All charts have data tables as a nonvisual alternative. Keyboard users can use
Tab/Enter/Space on chart points and buttons. The narrow layout stacks panels;
wide tables and the heatmap scroll within their panels, not the whole page.

The current-report strip is separate from historical filters. Its numbers describe
the last manual refresh, not continuously updated availability. Date/day/hour
filters do not apply to that strip; station selection does. For return guidance,
open **Find a return dock** (`/demo`), which retains the original freshness rules.

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

The dashboard is local FastAPI-served HTML/CSS/JavaScript, with no new frontend
framework or package dependency. Power BI authoring, live model orchestration and
held-out forecast evidence remain separately pending, as recorded in `PLANS.md`.

## Verification and maintenance

`make test` runs fixture/unit/API and disposable PostgreSQL integration tests,
including null denominators, weighted aggregation, DST date bounds, filters,
default range limits, provenance isolation, SQL permissions and idempotency.
Browser checks cover desktop/mobile, filters, chart inspection, CSV download,
empty results and the original finder. Synthetic-mode checks are not live evidence.

For local operation use `make status`, `make logs`, `make doctor`, and `make stop`.
Watch free disk space: one-minute historical collection grows even while the UI is
closed. No automatic host-disk cleanup or maintenance scheduler is promised.
