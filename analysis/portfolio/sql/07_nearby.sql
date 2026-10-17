-- Exploratory, simultaneous comparison, NOT arrival or backup success.
-- Select the 10 highest full-rate stations meeting declared support rules.
-- For each unique full report, inspect the nearest other operational station
-- in the SAME retrieved feed, using metadata stored with that observation.
WITH targets AS (
 SELECT station_id FROM study_station
 WHERE reports>=:station_min_reports AND observed_days>=:station_min_days
 ORDER BY full_reports::double precision/reports DESC,station_id LIMIT 10
), full_reports AS (
 SELECT e.* FROM study_eligible e JOIN targets t USING(station_id)
 WHERE num_docks_available=0 AND lat BETWEEN 43 AND 45 AND lon BETWEEN -80 AND -78
), pairs AS (
 SELECT f.station_id,f.snapshot_id,f.retrieved_at,n.station_id AS nearby_id,
   m.name AS nearby_name,n.num_docks_available,
   6371000*2*asin(sqrt(least(1.0,
     power(sin(radians(m.lat-f.lat)/2),2)+cos(radians(f.lat))*cos(radians(m.lat))
     *power(sin(radians(m.lon-f.lon)/2),2)))) AS distance_m
 FROM full_reports f JOIN station_snapshots n ON n.feed_fetch_id=f.feed_fetch_id
   AND n.station_id<>f.station_id AND n.is_canonical
   AND extract(epoch FROM n.retrieved_at-n.source_last_reported) BETWEEN -30 AND :fresh_seconds
   AND n.provenance_kind='live' AND n.ingested_at<:'end_utc_exclusive'::timestamptz
   AND n.retrieved_at>=:'start_utc'::timestamptz
   AND n.retrieved_at<:'end_utc_exclusive'::timestamptz
   AND n.is_installed IS TRUE AND n.is_returning IS TRUE
   AND n.num_docks_available IS NOT NULL
 JOIN station_metadata_versions m ON m.id=n.metadata_version_id AND m.known_from_at<=n.ingested_at
   AND m.lat BETWEEN f.lat-0.008 AND f.lat+0.008
   AND m.lon BETWEEN f.lon-0.011 AND f.lon+0.011
), nearest AS (
 SELECT DISTINCT ON(snapshot_id,retrieved_at) * FROM pairs
 WHERE distance_m<=:nearby_radius_m
 ORDER BY snapshot_id,retrieved_at,distance_m,nearby_id
), denominators AS (
 SELECT station_id,count(*) AS full_reports FROM full_reports GROUP BY 1
)
SELECT d.station_id,d.full_reports,count(n.snapshot_id) AS matched_reports,
 count(n.snapshot_id) FILTER(WHERE n.num_docks_available>0) AS nearby_available_reports,
 avg(n.distance_m) AS mean_distance_m,
 string_agg(DISTINCT n.nearby_id||' '||n.nearby_name,'; ') AS nearby_stations
FROM denominators d LEFT JOIN nearest n USING(station_id)
GROUP BY 1,2 ORDER BY 1;
