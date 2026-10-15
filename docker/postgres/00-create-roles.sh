#!/bin/sh
set -eu
script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

create_or_update_role() {
  role_name=$1
  role_password=$2
  psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set=ON_ERROR_STOP=1 \
    --set=role_name="$role_name" \
    --set=role_password="$role_password" \
    --file="$script_directory/helpers/role.sql"
}

create_or_update_role bikeshare_ingest "$BIKESHARE_INGEST_PASSWORD"
create_or_update_role bikeshare_api "$BIKESHARE_API_PASSWORD"
create_or_update_role bikeshare_reporter "$BIKESHARE_REPORTER_PASSWORD"
