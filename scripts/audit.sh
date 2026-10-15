#!/bin/sh
set -eu

echo "Project audit (secret values are never printed)"
echo "OS: $(uname -s) $(uname -m)"
sw_vers -productVersion 2>/dev/null | sed 's/^/macOS: /' || true
for command_name in git python3 uv docker; do
  if command -v "$command_name" >/dev/null 2>&1; then
    case "$command_name" in
      git) git --version ;;
      python3) python3 --version ;;
      uv) uv --version ;;
      docker) docker --version ; python3 scripts/manage.py compose version ;;
    esac
  else
    echo "$command_name: unavailable"
  fi
done

if [ -f .env ]; then
  echo "Configured environment names:"
  sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/  \1/p' .env
else
  echo ".env: absent (make start creates secure local configuration)"
fi

if command -v docker >/dev/null 2>&1 && [ -f .env ]; then
  python3 scripts/manage.py compose config --quiet
  echo "Compose configuration: valid"
else
  echo "Compose configuration: not checked"
fi
