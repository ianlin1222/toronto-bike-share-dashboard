-- Run with psql and a secret supplied at execution time, never in source control:
-- psql "$BIKESHARE_ADMIN_URL" -v reporter_password='...' -f sql/reporting/002_reporter_role.sql
\set ON_ERROR_STOP on

DO $role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bikeshare_reporter') THEN
    CREATE ROLE bikeshare_reporter LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END
$role$;

ALTER ROLE bikeshare_reporter PASSWORD :'reporter_password';
ALTER ROLE bikeshare_reporter SET statement_timeout = '30s';

REVOKE ALL ON SCHEMA public FROM bikeshare_reporter;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM bikeshare_reporter;
GRANT CONNECT ON DATABASE :DBNAME TO bikeshare_reporter;
GRANT USAGE ON SCHEMA reporting TO bikeshare_reporter;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO bikeshare_reporter;
ALTER DEFAULT PRIVILEGES IN SCHEMA reporting
  GRANT SELECT ON TABLES TO bikeshare_reporter;
