#!/usr/bin/env bash
# Scaffold a new dashboard spec from the template, ready to fill in.
#
#   scripts/new-dashboard.sh <category> <slug> "<Human / Title>"
#   scripts/new-dashboard.sh kubernetes jobs "Kubernetes / Jobs & CronJobs"
#
# Creates tools/specs/<category>/<slug>.yaml, then run `make build`.
set -euo pipefail
cd "$(dirname "$0")/.."

cat="${1:-}"; slug="${2:-}"; title="${3:-}"
[ -n "$cat" ] && [ -n "$slug" ] && [ -n "$title" ] \
  || { echo "usage: new-dashboard.sh <category> <slug> \"<Title>\""; exit 1; }

path="tools/specs/${cat}/${slug}.yaml"
[ -e "$path" ] && { echo "already exists: $path"; exit 1; }
mkdir -p "$(dirname "$path")"

cat > "$path" <<YAML
title: ${title}
description: >-
  One or two sentences: the operational question this dashboard answers.
datasource: prometheus
tags: [${cat}]
seo_phrase: ${title} Grafana dashboard
refresh: 30s
time_from: now-6h

questions:
  - "Replace me — the first thing on-call needs to know."

production_lessons: >-
  Why this dashboard exists and how it has earned its place in production.

data_sources:
  - "Which exporter(s) and metric families this needs."

templating:
  - name: job
    label: Job
    query: label_values(up, job)
    multi: false
    includeAll: false

rows:
  - title: Headline — read first
    panels:
      - type: stat
        title: Replace me
        unit: short
        thresholds:
          - {color: green, value: null}
          - {color: red, value: 1}
        targets:
          - expr: vector(0)
            instant: true
            legend: value

alerts: []
YAML

echo "✓ Created $path"
echo "  Edit it (see docs/authoring-specs.md), then run: make build && make validate"
