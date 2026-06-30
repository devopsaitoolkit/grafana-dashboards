#!/usr/bin/env bash
# Export a dashboard from a running Grafana by UID and normalise it into the
# portable, shareable form (datasources replaced by ${DS_*} inputs) so it can be
# committed. Useful when you have edited a dashboard in the Grafana UI.
#
#   scripts/export-dashboard.sh <uid> [output.json]
#
# Requires GRAFANA_URL + GRAFANA_TOKEN (see lib.sh).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$DIR/lib.sh"
need curl; need jq

uid="${1:-}"; out="${2:-}"
[ -n "$uid" ] || die "usage: export-dashboard.sh <uid> [output.json]"

log "Fetching dashboard $uid"
raw="$(api GET "/api/dashboards/uid/${uid}")"

# Strip instance-specific ids and replace concrete datasource uids with inputs.
normalised="$(echo "$raw" | jq '
  .dashboard
  | .id = null
  | walk(if type == "object" and has("datasource") and (.datasource | type) == "object"
         then .datasource.uid = (if .datasource.type == "loki" then "${DS_LOKI}" else "${DS_PROMETHEUS}" end)
         else . end)')"

if [ -n "$out" ]; then
  echo "$normalised" | jq . > "$out"
  log "Wrote $out"
else
  echo "$normalised" | jq .
fi
