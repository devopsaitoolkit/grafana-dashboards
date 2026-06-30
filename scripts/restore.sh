#!/usr/bin/env bash
# Restore a directory of dashboard JSON back into Grafana (e.g. from backup.sh or
# from this repo). Thin wrapper over import-dashboard.sh.
#
#   scripts/restore.sh <dir>           # imports every *.json under <dir>
#
# Requires GRAFANA_URL + GRAFANA_TOKEN (see lib.sh).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$DIR/lib.sh"

src="${1:-}"
[ -d "$src" ] || die "usage: restore.sh <dir-of-json>"

mapfile -t files < <(find "$src" -name '*.json' | sort)
[ "${#files[@]}" -gt 0 ] || die "no JSON files under $src"
log "Restoring ${#files[@]} dashboards from $src"
"$DIR/import-dashboard.sh" "${files[@]}"
