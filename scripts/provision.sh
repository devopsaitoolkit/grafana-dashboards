#!/usr/bin/env bash
# Lay out the dashboards in this repo for Grafana's file-based provisioning.
# Copies dashboards/** into a target directory (preserving the folder tree, which
# Grafana surfaces as nested dashboard folders) and prints the provider YAML to
# drop into /etc/grafana/provisioning/dashboards/.
#
#   scripts/provision.sh /var/lib/grafana/dashboards
set -euo pipefail
cd "$(dirname "$0")/.."

dest="${1:-}"
[ -n "$dest" ] || { echo "usage: provision.sh <target-dir>"; exit 1; }

mkdir -p "$dest"
cp -r dashboards/. "$dest/"
echo "✓ Copied $(find dashboards -name '*.json' | wc -l | tr -d ' ') dashboards into $dest"
cat <<YAML

# --- /etc/grafana/provisioning/dashboards/devopsaitoolkit.yaml ---
apiVersion: 1
providers:
  - name: devopsaitoolkit
    orgId: 1
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: ${dest}
      foldersFromFilesStructure: true
YAML
echo "# Reload Grafana (or wait updateIntervalSeconds) to pick the dashboards up."
echo "# See datasources/ for matching datasource provisioning."
