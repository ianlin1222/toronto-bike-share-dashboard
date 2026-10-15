# Three-page report specification

## Station availability patterns

- Toronto station map using latitude/longitude and station name; color by full-rate.
- Toronto-local hour × weekday heatmap of average docks or full-observation rate.
- Hourly dock trend with station and data-source filters.
- Cards for observation coverage, source age, and latest refresh.

## Model and recommendation performance

- A prominent Performance Evidence Label card. It must say Pending when there are
  no measured rows.
- Four-policy comparison for conditional and end-to-end success with numerator,
  denominator, coverage, and day-block interval visible in tooltip/table.
- Horizon, peak/off-peak, scarcity, model, and evaluation-run filters.
- Reliability plot (mean predicted vs observed) and distance/uplift trade-off.

## Ingestion and data-quality health

- Poll success/partial/failure trend and gap indicators.
- Station-record coverage, quarantines, stale rate, missing metadata, and latency.
- Storage-growth visual once measured summaries exist.
- Latest source, aggregate, evaluation, model, and Power BI refresh timestamps.
