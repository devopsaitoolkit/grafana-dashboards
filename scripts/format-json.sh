#!/usr/bin/env bash
# Canonicalise dashboard JSON formatting (2-space indent, trailing newline).
# Because dashboards are generated, the source of truth is the spec — this just
# re-runs the generator. Use it to normalise after any manual experimentation.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m tools.dashgen.build --quiet
echo "✓ dashboards regenerated and formatted from tools/specs/"
