SELECT local_hour, CASE WHEN weekday>=6 THEN 'Weekend' ELSE 'Weekday' END AS day_type,
 count(*) AS reports, count(*) FILTER(WHERE num_docks_available>0) AS available_reports,
 sum(num_docks_available) AS docks_sum,
 count(DISTINCT local_date) AS observed_days, count(DISTINCT station_id) AS stations
FROM study_eligible GROUP BY 1,2 ORDER BY 2,1;
