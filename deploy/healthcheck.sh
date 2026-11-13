#!/bin/sh
# Probe the live ask backend.  Exit 0 only when the engine is loaded.
#   ./healthcheck.sh                       # local
#   ./healthcheck.sh https://host          # remote
set -eu
BASE="${1:-http://127.0.0.1:8080}"
OUT="$(curl -fsS -m 10 "$BASE/public/brain/health")" || {
	echo "FAIL $BASE/public/brain/health unreachable" >&2
	exit 1
}
echo "$OUT"
echo "$OUT" | grep -q '"ready": *true' || {
	echo "FAIL engine not ready yet (loading or error)" >&2
	exit 1
}
echo "OK $BASE"
