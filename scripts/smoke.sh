#!/bin/sh
set -eu

base_url=${BIKESHARE_BASE_URL:-http://127.0.0.1:8080}
curl --fail --silent --show-error "$base_url/livez"
curl --fail --silent --show-error "$base_url/readyz"
curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  -d '{"destination":{"lat":43.6532,"lon":-79.3832},"horizon_minutes":15,"radius_m":750}' \
  "$base_url/v1/recommendations"
echo
