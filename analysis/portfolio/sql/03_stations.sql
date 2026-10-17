WITH names AS (
 SELECT DISTINCT ON(station_id) station_id,name,lat,lon,capacity
 FROM study_eligible ORDER BY station_id,retrieved_at DESC,snapshot_id DESC
)
SELECT s.*, n.name, n.lat, n.lon, n.capacity,
 available_reports::double precision/reports AS availability_rate,
 full_reports::double precision/reports AS full_rate,
 docks_sum::double precision/reports AS average_docks,
 reports>=:station_min_reports AND observed_days>=:station_min_days AS ranking_eligible,
 dense_rank() OVER(ORDER BY full_reports::double precision/reports DESC) AS full_rate_rank_all
FROM study_station s JOIN names n USING(station_id) ORDER BY station_id;
