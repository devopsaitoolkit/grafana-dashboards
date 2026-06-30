#!/usr/bin/env bash
# Validate every dashboard JSON and alert rule locally (the CI gate, runnable
# offline). Rebuilds from specs, runs the strict validator and the schema check.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v python3 >/dev/null || { echo "python3 required"; exit 1; }

echo "› Building dashboards from specs ..."
python3 -m tools.dashgen.build --quiet

echo "› Strict validation ..."
python3 -m tools.dashgen.validate

echo "› JSON Schema check ..."
python3 tools/dashgen/schema_check.py

echo "› JSON well-formedness ..."
fail=0
while IFS= read -r f; do
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$f" || { echo "invalid: $f"; fail=1; }
done < <(find dashboards -name '*.json')
[ "$fail" -eq 0 ] && echo "✓ all dashboards valid" || exit 1
