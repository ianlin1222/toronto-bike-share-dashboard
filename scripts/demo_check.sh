#!/bin/sh
set -eu

base_url=${BIKESHARE_BASE_URL:-http://127.0.0.1:8080}
curl --fail --silent --show-error "$base_url/readyz" >/dev/null
curl --fail --silent --show-error "$base_url/demo" >/dev/null
echo "Demo is available at $base_url/demo"
