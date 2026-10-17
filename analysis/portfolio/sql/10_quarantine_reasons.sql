-- A record can have multiple codes; these counts must not be summed as a total.
SELECT code,count(*) AS record_code_occurrences
FROM quarantine_records q JOIN poll_batches b ON b.id=q.batch_id
JOIN source_datasets d ON d.id=b.source_id
CROSS JOIN LATERAL unnest(q.validation_codes) code
WHERE d.source_kind='live' AND b.scheduled_at>=:'start_utc'::timestamptz
 AND b.scheduled_at<:'end_utc_exclusive'::timestamptz
GROUP BY code ORDER BY record_code_occurrences DESC,code;
