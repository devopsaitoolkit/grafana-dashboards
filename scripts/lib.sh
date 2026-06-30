#!/usr/bin/env bash
# Shared helpers for the dashboard scripts.
#
# Configuration via environment (never hardcode secrets in this repo):
#   GRAFANA_URL    Grafana base URL              (default http://localhost:3000)
#   GRAFANA_TOKEN  Grafana API token (Bearer)    — required for API calls
#   GRAFANA_FOLDER Target folder UID for imports  (optional)
#
# Export a token in your shell, e.g.:
#   export GRAFANA_URL=https://grafana.example.com
#   export GRAFANA_TOKEN=glsa_xxx        # create under Administration > Service accounts
set -euo pipefail

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_TOKEN="${GRAFANA_TOKEN:-}"

log()  { printf '\033[0;36m›\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[0;33m!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "required tool not found: $1"; }

require_token() {
  [ -n "$GRAFANA_TOKEN" ] || die "set GRAFANA_TOKEN (a Grafana service-account token) to use the API"
}

# api METHOD PATH [JSON_BODY]
api() {
  local method="$1" path="$2" body="${3:-}"
  require_token
  if [ -n "$body" ]; then
    curl -fsSL -X "$method" "${GRAFANA_URL}${path}" \
      -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
      -H "Content-Type: application/json" \
      --data "$body"
  else
    curl -fsSL -X "$method" "${GRAFANA_URL}${path}" \
      -H "Authorization: Bearer ${GRAFANA_TOKEN}"
  fi
}

repo_root() { git rev-parse --show-toplevel 2>/dev/null || pwd; }
