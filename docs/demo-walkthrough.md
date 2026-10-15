# Five-minute interview walkthrough

1. Start with `make start` and open `/dashboard`. Explain average reported docks,
   observed availability and collection coverage. A timeline gap means missing
   observations, not zero docks. Availability is not recommendation success.
   Apply date, station and local-hour filters. Open **View data**, explore the
   station table and export a CSV. For `make demo`, explicitly identify the
   synthetic-data banner. Then open **Find a return dock** at `/demo`.
2. Submit City Hall, 15 minutes, 750 m. Explain common ETA, geographic distance,
   primary versus distinct alternative, current dock evidence, data age, and the
   “does not reserve” notice.
3. Show `/docs`, reject an unsupported 12-minute horizon, and show the prediction
   endpoint returning `503 model_unavailable` before validation.
4. Show one `station_snapshots` row next to its `feed_fetches` and raw SHA-256;
   distinguish source report, retrieval and ingestion clocks and metadata history.
5. Show feature/label tests and the future-ingestion sentinel. Explain why trip
   records cannot become dock labels and why fixture metrics are non-approvable.
6. Show the Power BI Pending performance card specification and `PLANS.md`. State
   measured software results separately from the 84-day evidence gate.
