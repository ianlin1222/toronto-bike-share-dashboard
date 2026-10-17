WITH conflicts AS (
 SELECT station_id,source_last_reported FROM study_raw
 WHERE is_canonical AND source_last_reported IS NOT NULL
 GROUP BY 1,2 HAVING count(DISTINCT (num_docks_available,is_installed,is_returning))>1
)
SELECT 'Exclude same-timestamp conflicts' AS rule,count(*) AS reports,
 count(*) FILTER(WHERE e.num_docks_available>0) AS available_reports
FROM study_eligible e LEFT JOIN conflicts c USING(station_id,source_last_reported)
WHERE c.station_id IS NULL;
