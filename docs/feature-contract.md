# Feature and label contract v1

The schema name/order is fixed in `src/bikeshare/features/schema.py` and hashed into
every artifact. Both training and serving call the same feature builder. Loading
fails closed on a name, order, type, version, or hash mismatch.

- Temporal: Toronto local hour/weekday/weekend, cyclic day/week encodings, horizon, UTC
  offset, and DST flag.
- Spatial: point-in-time location, nearest-neighbour distance, and station density
  within 250/500/750 m.
- Utilization: publisher-reported docks/bikes/disabled counts, capacity-valid
  ratios, operational flags and missingness flags.
- Rolling demand proxies: time-weighted dock and bike averages, first/last changes,
  elapsed-time slopes and per-minute change volatility over 5/15/30 minutes.
- Nearby: nearest five other metadata-valid stations within 1 km; fresh count,
  mean distance, dock total, capacity-weighted dock ratio, full proportion and mean
  15-minute trend.

Only records with both `retrieved_at <= decision_time` and
`ingested_at <= decision_time` are eligible. Metadata must have been known then.
Values carry for at most five minutes. Rolling statistics require at least 80%
time coverage and three distinct source reports; otherwise values are null and
coverage/missing flags are emitted. Neighbour counts always distinguish expected
from fresh observed neighbours. Outages are never arbitrarily filled.

The generic-bicycle target assumes a functional total reported Toronto dock can
accept the rider's bicycle. Standing scooters are excluded from bicycle counts,
while compatibility arrays are retained for future exact-type handling.
