#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 scripts/manage.py start --open
result=$?
if [ "$result" -ne 0 ]; then
  printf '\nPress Enter to close this window.'
  read -r answer
fi
exit "$result"
