BEGIN;

CREATE SCHEMA IF NOT EXISTS reporting;

CREATE OR REPLACE VIEW reporting.v_station_current
WITH (security_barrier = true) AS
SELECT
    station.station_id,
    station.lifecycle_state,
    metadata.name,
    metadata.address,
    metadata.lat,
    metadata.lon,
    metadata.capacity,
    metadata.known_from_at AS metadata_known_from_at,
    metadata.metadata_hash
FROM stations station
JOIN station_metadata_versions metadata
  ON metadata.station_id = station.station_id
 AND metadata.known_to_at IS NULL;

CREATE OR REPLACE VIEW reporting.v_station_hourly_availability
WITH (security_barrier = true) AS
SELECT
    summary.local_hour_start,
    (summary.local_hour_start AT TIME ZONE 'America/Toronto')::date AS local_date,
    extract(hour FROM summary.local_hour_start AT TIME ZONE 'America/Toronto')::smallint
        AS local_hour,
    extract(isodow FROM summary.local_hour_start AT TIME ZONE 'America/Toronto')::smallint
        AS local_weekday,
    summary.station_id,
    current.name,
    current.lat,
    current.lon,
    current.capacity,
    summary.source_kind,
    summary.observation_count,
    summary.operational_observation_count,
    summary.average_docks,
    summary.minimum_docks,
    summary.full_observation_count,
    summary.fresh_coverage_rate,
    summary.computed_at
FROM station_hourly_summary summary
JOIN reporting.v_station_current current USING (station_id);

CREATE OR REPLACE VIEW reporting.v_recommendation_performance
WITH (security_barrier = true) AS
SELECT
    metrics.evaluation_run_id,
    run.model_run_id,
    run.split_name,
    run.protocol_hash,
    metrics.policy_id,
    metrics.horizon_minutes,
    metrics.stratum_name,
    metrics.stratum_value,
    metrics.successes,
    metrics.known_recommendation_outcomes,
    metrics.protocol_requests,
    metrics.otherwise_evaluable_requests,
    metrics.abstentions,
    metrics.missing_outcomes,
    metrics.exclusions,
    metrics.conditional_success_rate,
    metrics.coverage_rate,
    metrics.end_to_end_success_rate,
    metrics.matched_baseline_success_rate,
    metrics.percentage_point_uplift,
    metrics.ci_lower,
    metrics.ci_upper,
    metrics.median_distance_m,
    metrics.p90_distance_m,
    metrics.median_extra_distance_m,
    metrics.computed_at,
    CASE
      WHEN run.status = 'complete' THEN 'Measured offline hypothetical replay'
      ELSE 'Pending—insufficient validated history'
    END AS evidence_status
FROM evaluation_metrics metrics
JOIN evaluation_runs run ON run.id = metrics.evaluation_run_id;

CREATE OR REPLACE VIEW reporting.v_model_calibration
WITH (security_barrier = true) AS
SELECT
    bins.model_run_id,
    model.algorithm,
    model.feature_version,
    bins.split_name,
    bins.horizon_minutes,
    bins.bin_number,
    bins.lower_probability,
    bins.upper_probability,
    bins.mean_predicted_probability,
    bins.observed_success_rate,
    bins.example_count,
    model.created_at AS model_created_at
FROM model_calibration_bins bins
JOIN model_runs model ON model.id = bins.model_run_id;

CREATE OR REPLACE VIEW reporting.v_ingestion_health
WITH (security_barrier = true) AS
SELECT
    date_trunc('hour', batch.scheduled_at) AS utc_hour,
    source.source_kind,
    source.system_id,
    count(*) AS scheduled_polls,
    count(*) FILTER (WHERE batch.status = 'success') AS successful_polls,
    count(*) FILTER (WHERE batch.status = 'partial') AS partial_polls,
    count(*) FILTER (WHERE batch.status = 'failed') AS failed_polls,
    avg(batch.latency_ms) AS average_latency_ms,
    sum(batch.expected_records) AS expected_station_records,
    sum(batch.accepted_records) AS accepted_station_records,
    sum(batch.quarantined_records) AS quarantined_records,
    avg(
      CASE WHEN batch.expected_records > 0
        THEN batch.accepted_records::double precision / batch.expected_records
      END
    ) AS average_station_coverage,
    max(batch.ended_at) AS latest_completed_at
FROM poll_batches batch
JOIN source_datasets source ON source.id = batch.source_id
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW reporting.v_refresh_status
WITH (security_barrier = true) AS
SELECT
    now() AS database_viewed_at,
    (SELECT max(retrieved_at) FROM station_snapshots) AS latest_source_retrieval_at,
    (SELECT max(source_last_reported) FROM station_snapshots WHERE is_canonical)
        AS latest_station_report_at,
    (SELECT max(computed_at) FROM station_hourly_summary) AS latest_availability_aggregate_at,
    (SELECT max(computed_at) FROM pipeline_daily_summary) AS latest_health_aggregate_at,
    (SELECT max(completed_at) FROM evaluation_runs WHERE status = 'complete')
        AS latest_evaluation_at,
    (SELECT max(activated_at) FROM model_runs WHERE status = 'active') AS active_model_at;

COMMIT;
