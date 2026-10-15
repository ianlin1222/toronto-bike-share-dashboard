# Power BI semantic model

Use Import mode. Query the six `reporting.v_*` views through the
`bikeshare_reporter` role.

Tables and relationships:

| Power BI table | Source view | Key / relationship |
|---|---|---|
| Station | `v_station_current` | `station_id` unique; 1:* to Station Availability |
| Station Availability | `v_station_hourly_availability` | many side on `station_id`; local date joins Date |
| Recommendation Performance | `v_recommendation_performance` | standalone aggregate; horizon/policy fields drive slicers |
| Model Calibration | `v_model_calibration` | model run and horizon filter; no bidirectional relationship |
| Ingestion Health | `v_ingestion_health` | UTC hour joins Date/Time only when a dedicated hour dimension exists |
| Refresh Status | `v_refresh_status` | single-row disconnected status table |

Create a standard Date table spanning Station Availability local dates. Mark it
as the date table and use single-direction relationships. Do not connect aggregate
facts to each other or turn on bidirectional filtering to make a visual work.
