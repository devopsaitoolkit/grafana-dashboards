#!/usr/bin/env bash
# Import one or more dashboard JSON files into Grafana via the HTTP API.
#
#   scripts/import-dashboard.sh dashboards/linux/cpu.json [more.json ...]
#
# Datasource inputs (${DS_PROMETHEUS} / ${DS_LOKI}) are resolved automatically to
# the Grafana datasource named by $DS_PROMETHEUS_NAME / $DS_LOKI_NAME (defaults
# "Prometheus" / "Loki"). Requires GRAFANA_URL + GRAFANA_TOKEN (see lib.sh).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$DIR/lib.sh"
need curl; need jq

[ "$#" -ge 1 ] || die "usage: import-dashboard.sh <file.json> [...]"

DS_PROMETHEUS_NAME="${DS_PROMETHEUS_NAME:-Prometheus}"
DS_LOKI_NAME="${DS_LOKI_NAME:-Loki}"
FOLDER_UID="${GRAFANA_FOLDER:-}"

for file in "$@"; do
  [ -f "$file" ] || die "not found: $file"
  log "Importing $file"
  # Build the inputs array expected by /api/dashboards/import from __inputs.
  inputs="$(jq -c --arg prom "$DS_PROMETHEUS_NAME" --arg loki "$DS_LOKI_NAME" '
    [(.__inputs // [])[] | {
      name: .name,
      type: "datasource",
      pluginId: .pluginId,
      value: (if .pluginId == "loki" then $loki else $prom end)
    }]' "$file")"
  payload="$(jq -c --argjson inputs "$inputs" --arg folder "$FOLDER_UID" '
    {dashboard: (del(.__inputs) | del(.__requires) | .id = null),
     overwrite: true,
     inputs: $inputs,
     folderUid: (if $folder == "" then null else $folder end)}' "$file")"
  result="$(api POST /api/dashboards/import "$payload")"
  echo "$result" | jq -r '"  ✓ \(.title // "imported")  ->  \(.importedUrl // .url // "ok")"'
done
