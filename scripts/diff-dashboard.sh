#!/usr/bin/env bash
# Compare a dashboard in this repo against the live copy in Grafana (by UID), so
# you can see what drifted before re-importing or exporting.
#
#   scripts/diff-dashboard.sh dashboards/linux/cpu.json
#
# Requires GRAFANA_URL + GRAFANA_TOKEN (see lib.sh) and `jq`. Compares the
# meaningful panel/templating structure, ignoring volatile ids and versions.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$DIR/lib.sh"
need curl; need jq

file="${1:-}"
[ -f "$file" ] || die "usage: diff-dashboard.sh <file.json>"
uid="$(jq -r '.uid' "$file")"
[ -n "$uid" ] && [ "$uid" != "null" ] || die "no uid in $file"

norm='del(.id,.version,.iteration,.__inputs,.__requires)
      | (.panels // []) |= sort_by(.id)
      | walk(if type=="object" then del(.id) else . end)'

local_json="$(jq "$norm" "$file")"
live_json="$(api GET "/api/dashboards/uid/${uid}" | jq ".dashboard | $norm")"

if diff <(echo "$local_json") <(echo "$live_json") >/dev/null; then
  log "No structural difference for $uid"
else
  warn "Differences for $uid (< repo, > live):"
  diff <(echo "$local_json") <(echo "$live_json") || true
fi
