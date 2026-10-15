# Build and verification on Windows

Status: **support assets ready; report artifact not yet built or verified**.
This directory is not a substitute for a `.pbix`/PBIP. M6 stays blocked until the
steps below are completed in a current supported Power BI Desktop on Windows.

1. Start the PostgreSQL database and apply `sql/reporting/001_views.sql`.
2. As an administrator, create the `bikeshare_reporter` login with
   `sql/reporting/002_reporter_role.sql`, supplying the password only at runtime.
3. In Power BI Desktop choose **Get Data → PostgreSQL database**, connect with the
   reporting login, and choose **Import**. Select the six original `reporting.v_*`
   views listed in `relationships.md`. The v0.2 migration adds an optional seventh
   view, `v_dashboard_station_hours`, with source-separated observation counts/sums.
4. Rename queries to Station, Station Availability, Recommendation Performance,
   Model Calibration, Ingestion Health, and Refresh Status. Apply the relationships
   in `relationships.md`, import `theme.json`, then create the measures in
   `measures.dax`.
5. Build pages named **Station availability patterns**, **Model and recommendation
   performance**, and **Ingestion and data-quality health**. Follow
   `visual-spec.md`. The performance page must render the Pending evidence card
   when no complete evaluation exists.
6. Refresh. Verify row counts against each SQL view, null forecasts/results,
   timestamps, map coordinates, filters, and the read-only permission test.
7. Save `BikeShareDockAvailability.pbix` or a supported PBIP project here. Record
   the Desktop version/date, refresh evidence, relationship screenshot, three page
   screenshots, and PDF export in `verification.md`.

Publication, Power BI Service credentials, a gateway, and paid licensing are not
authorized. Local Windows Desktop verification alone is the current requirement.
