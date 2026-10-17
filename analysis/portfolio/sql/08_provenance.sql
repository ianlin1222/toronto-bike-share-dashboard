SELECT count(*) AS status_fetches, count(DISTINCT f.raw_sha256) AS distinct_status_bodies,
 min(f.retrieved_at) AS first_fetch_utc,max(f.retrieved_at) AS last_fetch_utc,
 encode(sha256(convert_to(string_agg(f.id::text||':'||f.raw_sha256::text,',' ORDER BY f.id),'UTF8')),'hex')
   AS ordered_fetch_id_and_body_hash_fingerprint
FROM feed_fetches f JOIN (SELECT DISTINCT feed_fetch_id FROM study_raw) r ON r.feed_fetch_id=f.id;
