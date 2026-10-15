# Local operations runbook

## Start and verify

1. Install Docker Desktop under its applicable licence and enable start-at-login if
   this laptop is the collector host. Preventing sleep is an operator decision.
2. Run `make start` or double-click `Start.command`. Local credentials are generated
   only for missing/template values; a populated `.env` is preserved.
3. The launcher builds, migrates, starts collection and waits for fresh data.
4. Check `make status`, `curl http://127.0.0.1:8080/readyz`, and `make logs`.
   Open http://127.0.0.1:8080/demo. PostgreSQL is at localhost:55432.

Use `python3 scripts/manage.py compose …` for advanced Compose commands; this also
works when Docker Desktop's Compose plugin is not on the normal command path.
Database initialization scripts run only on an empty volume. Never delete a volume
to fix credentials. Existing database passwords must match `.env`.

The collector and API use `restart: unless-stopped`. Only one collector acquires
the PostgreSQL advisory lock. Laptop sleep, loss of network, or Docker shutdown
creates an explicit collection gap; the live feed cannot be silently backfilled.

## Failure behavior

- Network, 429 and 5xx responses retry at most three times with bounded backoff;
  ordinary 4xx failures are not retried.
- Invalid feed envelopes fail the batch and retain successfully retrieved raw
  evidence. Invalid station records are quarantined while good rows can proceed.
- Partial batches update valid stations but are flagged. Station freshness always
  uses `last_reported`, not the retrieval clock.
- SIGTERM/SIGINT finishes or rolls back the active transaction and records a
  shutdown event.
- Approved-model serving is not wired yet. The API remains a live baseline with
  null probabilities, including when validated mode is requested in configuration.
- Serving may reuse a city-wide database snapshot for up to two seconds. It never
  reuses a snapshot from a later decision time, and station age is recalculated for
  every request. Health checks bypass that cache; historical stores default to no cache.

## Backup and restore drill

For a local logical backup, write outside source control:

```sh
python3 scripts/manage.py compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > var/backup.dump
```

Restore only into a newly created test database, run row-count/hash checks, then
remove that test database. Never test restore over the collection database. Record
commands, PostgreSQL version, backup hash, row counts, and result in `PLANS.md`.

## Secrets and privacy

The app binds to localhost. `.env`, data volumes, raw history, model binaries and
exact rider locations are excluded from Git. API logs never include coordinates.
Persisted request destinations are rounded to three decimals; no user/device/account
identifiers exist. The planned 30-day request deletion schedule is not automated yet.
Until maintenance scheduling is accepted, run the documented archive job manually
and monitor disk usage with `make data-audit`.
