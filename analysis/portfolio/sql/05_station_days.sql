SELECT station_id,local_date,count(*) AS reports,
 count(*) FILTER(WHERE num_docks_available>0) AS available_reports,
 sum(num_docks_available) AS docks_sum,
 count(DISTINCT date_trunc('hour',retrieved_at)) AS observed_hours
FROM study_eligible GROUP BY 1,2 ORDER BY 1,2;
