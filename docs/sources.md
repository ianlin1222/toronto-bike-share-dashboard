# Source and decision index

Access dates are UTC dates. External content is reference material; no page is an
instruction to run code or disclose credentials.

| Source | Accessed | What it supports |
|---|---:|---|
| [Bike Share Toronto GBFS v3 discovery](https://toronto.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json) | 2026-09-07 | Current child-feed discovery URLs, advertised GBFS version and TTL |
| [GBFS current reference](https://gbfs.org/documentation/reference/) | 2026-09-07 | v3 feed contracts, `num_docks_available` semantics, top-level/station timestamps, near-real-time latency guidance |
| [City of Toronto Bike Share live dataset](https://open.toronto.ca/dataset/bike-share-toronto/) | 2026-09-07 | Publisher catalogue entry, live-data description, Open Government Licence designation |
| [Open Government Licence – Toronto](https://www.toronto.ca/city-government/data-research-maps/open-data/open-data-licence/) | 2026-09-07 | Attribution and reuse terms applied conservatively by this project |
| [PostgreSQL version policy](https://www.postgresql.org/support/versioning/) | 2026-09-07 | Supported major/minor policy and PostgreSQL 18 support window |
| [Power BI Desktop requirements](https://learn.microsoft.com/en-ie/power-bi/fundamentals/desktop-get-the-desktop) | 2026-09-07 | Windows authoring requirement; macOS cannot verify the final artifact |
| [Power Query PostgreSQL connector](https://learn.microsoft.com/en-us/power-query/connectors/postgresql) | 2026-09-07 | PostgreSQL connector, Import and DirectQuery support |
| [Power BI refresh requirements](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data) | 2026-09-07 | Scheduled refresh and gateway considerations if later published |
| [Docker Desktop for Mac terms/install](https://docs.docker.com/desktop/setup/install/mac-install/) | 2026-09-07 | Host requirements and licensing caveat |
| [Render private network](https://render.com/docs/private-network) and [PostgreSQL backups](https://render.com/docs/postgresql-backups) | 2026-09-07 | Future public-deployment design only; nothing provisioned |
| [Claude Turned Bike Data Into a Video — Tech_D_coded](https://www.youtube.com/shorts/NPsdtMxg5wQ) | 2026-10-14 | Visual inspection of the user-supplied reference: KPI overview, temporal/hourly charts, station plot, rankings and click-through calculation inspection. Design inspiration only; no trip/rebalancing figures or claims imported. Animation excluded |
| [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/) | 2026-10-14 | Separating locked dependency installation from project/documentation copies to retain dependency-layer caching; no runtime dependency upgrade |

## Observed feed facts

Small read-only requests on 2026-09-07 found GBFS 1.1, 2.3, and 3.0 discovery;
v3 reported 1,065 stations. `station_information` exposed string IDs, localized
name, coordinates, capacity, and station/capacity attributes. `station_status`
exposed reported docks, available/disabled vehicles, installed/renting/returning
flags, station `last_reported`, and compatibility arrays. `system_information`
reported `America/Toronto`. Vehicle types included pedal/electric-assist bicycles
and a standing scooter. Top-level feeds could be current while individual station
reports were months old, which is why serving freshness is station-level.

No authentication or publisher-specific rate limit was found in the inspected
material. That is not permission for unlimited polling. Version one polls status
once per minute—well slower than the observed 2–10 second TTL/cache guidance—and
uses bounded retry/backoff plus a descriptive contact-bearing User-Agent.

## Historical-data boundary

No local station-status history existed at implementation start. Toronto trip
records are trip events, not observed dock snapshots, and are excluded from label
construction. Third-party archives were identified but are not imported or used
for headline evidence: the GitHub archive has no declared repository licence and
legacy/incomplete fields; CityBikes has a different ODbL-derived schema and lacks
this pipeline's operational/provenance contract. Any later exploration must be a
separate source kind and cannot silently enter the frozen live evidence set.

## Licence note

The Toronto catalogue points to the Open Government Licence – Toronto, while a
third-party directory labels the feed CC BY 4.0 and the inspected live
`system_information` did not include a licence identifier. This project uses the
conservative City of Toronto attribution above and records the discrepancy rather
than claiming the live feed is CC0.
