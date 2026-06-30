#!/usr/bin/env bash
# Back up every dashboard from a running Grafana into a timestamped directory of
# portable JSON (datasource-templated), one file per dashboard.
#
#   scripts/backup.sh [output_dir]      # default: backups/<UTC-timestamp>
#
# Requires GRAFANA_URL + GRAFANA_TOKEN (see lib.sh). The timestamp is taken from
# the system clock at run time.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$DIR/lib.sh"
need curl; need jq

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${1:-backups/$stamp}"
mkdir -p "$out"
log "Backing up dashboards to $out"

count=0
api GET "/api/search?type=dash-db&limit=5000" | jq -r '.[].uid' | while read -r uid; do
  [ -n "$uid" ] || continue
  api GET "/api/dashboards/uid/${uid}" \
    | jq '.dashboard | .id = null' > "${out}/${uid}.json"
  count=$((count + 1))
  printf '  ✓ %s\n' "$uid" >&2
done
log "Backup complete: $out"
