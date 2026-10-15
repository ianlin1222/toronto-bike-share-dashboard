# Data dictionary

All persisted timestamps are PostgreSQL `timestamptz` and represent UTC instants.
Toronto-local calendar fields are derived with `America/Toronto`; UTC remains the
ordering key during daylight-saving folds.

| Entity | Grain | Critical semantics |
|---|---|---|
| `source_datasets` | Source/import contract | Keeps live, fixture, archive, and synthetic evidence distinguishable, with licence and importer version |
| `poll_batches` | Source × deterministic scheduled instant | Unique retry/restart key; success, partial, and failure are explicit |
| `feed_fetches` | Batch × feed × HTTP attempt | Retrieval/ingestion times, source update, TTL/cache evidence, body hash and validation state |
| `raw_payload_blobs` | Unique uncompressed SHA-256 | Immutable gzip evidence or verified archive URI; deduplicated across identical responses |
| `stations` | Station string ID | Lifecycle only; IDs are never cast to numeric |
| `station_metadata_versions` | Station × known-from version | Type-2 name/location/capacity history; “known” starts at ingestion, not source publication |
| `station_snapshots` | Feed fetch × station | Reported docks/bikes/disabled/status, all clocks, compatibility, quality flags and provenance; time-partitioned |
| `quarantine_records` | Invalid source record | Raw fragment plus explicit validation codes; never coerced into availability |
| `ingestion_events` | Operational event | Retry/failure/gap/restart/archive evidence with severity/code |
| `serving_feature_rows` | Station × feature version | Latest versioned feature JSON with as-of time, schema hash and coverage flags |
| `model_runs` | Training run | Time cutoffs, configuration, feature/extraction versions, seed, artifact hash, metrics and approval state |
| `evaluation_runs` | Frozen replay run | Protocol/model/policy/code hashes and split; test run cannot exist before freeze |
| `recommendation_requests` | API or replay request | Coarsened destination only, common horizon/radius, data/model/policy mode |
| `recommendation_results` | Request × policy × rank | Selected station, distance, current docks, nullable forecast, score and snapshot provenance |
| `evaluation_outcomes` | Evaluation request × policy × rank | Future match, known/unknown label, abstention/exclusion and report strata |
| `model_calibration_bins` | Model × split × horizon × decile | Observed/predicted probability reliability evidence |
| `evaluation_metrics` | Evaluation × policy × horizon × stratum | Frozen numerators, denominators, coverage, end-to-end result, uplift, intervals and distance |
| `dashboard_station_hours` | Station × UTC hour × source kind | Canonical, fresh, known-dock, positive-dock and known-bike counts; inventory sums and aggregation timestamp. Ratios use summed counts, not average-of-averages. Live API excludes other source kinds; reporter uses `v_dashboard_station_hours` |

`num_docks_available` is the publisher's reported count of functional docks able to
accept returns. It is not recomputed as capacity minus bikes and disabled docks are
not subtracted a second time. Missing fields remain null.
