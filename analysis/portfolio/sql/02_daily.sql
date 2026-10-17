WITH coverage AS (
 SELECT local_date, count(*) AS expected_minutes,
   count(*) FILTER(WHERE attempted) AS attempted_minutes,
   count(*) FILTER(WHERE successful) AS successful_minutes,
   count(*) FILTER(WHERE partial) AS partial_minutes,
   count(*) FILTER(WHERE failed) AS failed_minutes
 FROM study_minutes GROUP BY 1
), reports AS (
 SELECT local_date, count(*) AS reports,
   count(*) FILTER(WHERE num_docks_available>0) AS available_reports,
   sum(num_docks_available) AS docks_sum,
   count(DISTINCT station_id) AS stations
 FROM study_eligible GROUP BY 1
)
SELECT c.*, coalesce(r.reports,0) AS reports,
 coalesce(r.available_reports,0) AS available_reports,
 coalesce(r.docks_sum,0) AS docks_sum, coalesce(r.stations,0) AS stations
FROM coverage c LEFT JOIN reports r USING(local_date) ORDER BY local_date;
