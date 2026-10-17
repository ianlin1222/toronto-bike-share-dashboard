SELECT threshold AS fresh_seconds, count(*) AS reports,
 count(*) FILTER(WHERE num_docks_available>0) AS available_reports,
 count(DISTINCT station_id) AS stations
FROM study_unique CROSS JOIN (VALUES (60),(120),(300)) limits(threshold)
WHERE age_seconds BETWEEN -30 AND threshold
 AND is_installed IS TRUE AND is_returning IS TRUE AND num_docks_available IS NOT NULL
GROUP BY 1 ORDER BY 1;
