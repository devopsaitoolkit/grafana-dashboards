#!/usr/bin/env bash
# Render real PNG screenshots of imported dashboards using the Grafana image
# renderer (the committed *.svg files are schematics; this produces pixel
# captures once a dashboard is live).
#
#   scripts/screenshot.sh <uid> [output.png]
#
# Requires GRAFANA_URL + GRAFANA_TOKEN (see lib.sh) and the grafana-image-renderer
# plugin (or a remote renderer) configured on the Grafana server.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$DIR/lib.sh"
need curl

uid="${1:-}"
[ -n "$uid" ] || die "usage: screenshot.sh <uid> [output.png]"
out="${2:-${uid}.png}"
width="${WIDTH:-1600}"; height="${HEIGHT:-900}"

log "Rendering $uid -> $out (${width}x${height})"
curl -fsSL "${GRAFANA_URL}/render/d/${uid}/_?width=${width}&height=${height}&kiosk" \
  -H "Authorization: Bearer ${GRAFANA_TOKEN}" -o "$out"
log "Saved $out"
echo "Tip: set ?from=now-24h&to=now or &var-instance=... on the URL to frame the capture."
