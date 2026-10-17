SELECT
 (SELECT count(*) FROM study_raw) AS raw_rows,
 (SELECT count(*) FROM study_raw WHERE is_canonical) AS canonical_rows,
 (SELECT count(*) FROM study_raw WHERE is_canonical AND source_last_reported IS NULL) AS missing_report_time,
 (SELECT count(*) FROM study_unique) AS unique_reports,
 (SELECT count(*) FROM study_unique WHERE age_seconds NOT BETWEEN -30 AND :fresh_seconds) AS stale_unique_reports,
 (SELECT count(*) FROM study_unique WHERE age_seconds BETWEEN -30 AND :fresh_seconds) AS fresh_unique_reports,
 (SELECT count(*) FROM study_unique WHERE age_seconds BETWEEN -30 AND :fresh_seconds
   AND NOT (is_installed IS TRUE AND is_returning IS TRUE)) AS nonoperational_or_unknown_reports,
 (SELECT count(*) FROM study_unique WHERE age_seconds BETWEEN -30 AND :fresh_seconds
   AND is_installed IS TRUE AND is_returning IS TRUE AND num_docks_available IS NULL) AS missing_docks,
 (SELECT count(*) FROM study_eligible) AS eligible_reports,
 (SELECT count(*) FROM study_eligible WHERE num_docks_available>0) AS available_reports,
 (SELECT count(*) FROM study_eligible WHERE num_docks_available=0) AS full_reports,
 (SELECT sum(num_docks_available) FROM study_eligible) AS docks_sum,
 (SELECT count(DISTINCT station_id) FROM study_eligible) AS eligible_stations,
 (SELECT count(DISTINCT local_date) FROM study_eligible) AS observed_days,
 (SELECT count(*) FROM study_minutes) AS expected_minutes,
 (SELECT count(*) FROM study_minutes WHERE attempted) AS attempted_minutes,
 (SELECT count(*) FROM study_minutes WHERE successful) AS successful_minutes,
 (SELECT count(*) FROM study_minutes WHERE partial) AS partial_minutes,
 (SELECT count(*) FROM study_minutes WHERE failed) AS failed_minutes,
 (SELECT count(*) FROM study_eligible WHERE name IS NULL) AS missing_metadata_reports,
 (SELECT count(*) FROM study_eligible WHERE lat IS NULL OR lon IS NULL
    OR lat NOT BETWEEN 43 AND 45 OR lon NOT BETWEEN -80 AND -78) AS invalid_local_location_reports,
 (SELECT count(*) FROM study_eligible WHERE capacity IS NULL OR capacity=0) AS unknown_or_zero_capacity_reports,
 (SELECT count(*) FROM study_eligible WHERE capacity>0 AND num_docks_available>capacity) AS docks_exceed_capacity_reports,
 (SELECT count(*) FROM (
   SELECT station_id, source_last_reported FROM study_raw
   WHERE is_canonical AND source_last_reported IS NOT NULL
   GROUP BY 1,2 HAVING count(DISTINCT (num_docks_available,is_installed,is_returning))>1
 ) c) AS conflicting_report_timestamps,
 (SELECT count(*) FROM quarantine_records q JOIN poll_batches b ON b.id=q.batch_id
   JOIN source_datasets d ON d.id=b.source_id WHERE d.source_kind='live'
   AND b.scheduled_at>=:'start_utc'::timestamptz AND b.scheduled_at<:'end_utc_exclusive'::timestamptz) AS quarantined_records;
