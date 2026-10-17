-- Common CTE prefix prepended to each analysis SELECT by export.py.
-- No schema/data changes, gap filling or trip inference.
WITH study_raw AS MATERIALIZED (
SELECT s.snapshot_id,s.retrieved_at,s.station_id,s.feed_fetch_id,
       s.ingested_at,s.source_last_reported,s.is_canonical,
       s.is_installed,s.is_returning,s.num_docks_available,
       m.name, m.lat, m.lon, m.capacity,
       extract(epoch FROM s.retrieved_at-s.source_last_reported) AS age_seconds,
       (s.retrieved_at AT TIME ZONE :'timezone')::date AS local_date,
       extract(hour FROM s.retrieved_at AT TIME ZONE :'timezone')::int AS local_hour,
       extract(isodow FROM s.retrieved_at AT TIME ZONE :'timezone')::int AS weekday
FROM station_snapshots s
LEFT JOIN station_metadata_versions m ON m.id=s.metadata_version_id
  AND m.known_from_at<=s.ingested_at
WHERE s.retrieved_at>=:'start_utc'::timestamptz
  AND s.retrieved_at<:'end_utc_exclusive'::timestamptz
  AND s.ingested_at<:'end_utc_exclusive'::timestamptz
  AND s.provenance_kind='live'),

-- One record per station report timestamp. Repeated retrievals do not become
-- independent evidence. First canonical retrieval wins, even if a later retrieval
-- at the same source timestamp contains a correction. Conflict counts are audited.
study_unique AS MATERIALIZED (
SELECT * FROM (
  SELECT r.*, row_number() OVER (
    PARTITION BY station_id, source_last_reported
    ORDER BY retrieved_at, snapshot_id
  ) AS report_order
  FROM study_raw r WHERE is_canonical AND source_last_reported IS NOT NULL
) ranked WHERE report_order=1),

study_eligible AS MATERIALIZED (
SELECT * FROM study_unique
WHERE age_seconds BETWEEN -30 AND :fresh_seconds
  AND is_installed IS TRUE AND is_returning IS TRUE
  AND num_docks_available IS NOT NULL),

study_station AS (
SELECT station_id, count(*) AS reports,
  count(*) FILTER(WHERE num_docks_available>0) AS available_reports,
  count(*) FILTER(WHERE num_docks_available=0) AS full_reports,
  sum(num_docks_available) AS docks_sum,
  count(DISTINCT local_date) AS observed_days,
  count(DISTINCT date_trunc('hour',retrieved_at)) AS observed_hours,
  min(retrieved_at) AS first_observed_utc, max(retrieved_at) AS last_observed_utc
FROM study_eligible GROUP BY station_id),

-- Include unattempted minutes, not just logged batches, in completeness.
study_minutes AS (
WITH batches AS (
  SELECT date_trunc('minute',b.scheduled_at) AS minute,
    bool_or(b.status='success') AS successful,
    bool_or(b.status='partial') AS partial,
    bool_or(b.status='failed') AS failed
  FROM poll_batches b JOIN source_datasets d ON d.id=b.source_id
  WHERE d.source_kind='live'
    AND b.scheduled_at>=:'start_utc'::timestamptz
    AND b.scheduled_at<:'end_utc_exclusive'::timestamptz
  GROUP BY 1
)
SELECT minute, (minute AT TIME ZONE :'timezone')::date AS local_date,
       b.minute IS NOT NULL AS attempted,
       coalesce(successful,false) AS successful,
       coalesce(partial,false) AS partial, coalesce(failed,false) AS failed
FROM generate_series(:'start_utc'::timestamptz,
  :'end_utc_exclusive'::timestamptz-interval '1 minute',interval '1 minute') minute
LEFT JOIN batches b USING(minute))
