# Deployment status and future option

Current delivery is local-only and has no uptime promise. No public service,
managed database, object storage, Power BI publication, gateway, account, or paid
licence has been provisioned.

If separately approved, the plan's concrete public target is Render: one HTTPS web
service, one continuously running private worker, and paid managed PostgreSQL in
the same region/private network. PostgreSQL must not expose unrestricted public
access. Add secrets, database TLS, 60 recommendation requests/IP/minute,
request-size bounds, release migrations, smoke checks, managed point-in-time
recovery, nightly encrypted logical exports, and a tested restore.

The earlier planning estimate was approximately USD 21/month as a floor for three
entry-level paid components, plus storage, backups, bandwidth and tax. Prices must
be re-quoted before approval. Power BI publication/sharing and an always-on Windows
gateway are separate scope and cost decisions.
