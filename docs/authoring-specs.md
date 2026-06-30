# Authoring dashboard specs

Every dashboard in this repository is generated from a compact YAML **spec** under
`tools/specs/`. You never hand-write Grafana JSON. `make build` compiles each spec
into:

- `dashboards/<category>/<slug>.json` — the importable Grafana dashboard
- `docs/dashboards/<category>/<slug>.md` — a full documentation page
- `screenshots/<category>/<slug>.svg` — an annotated schematic
- `alerts/<domain>.rules.yml` — Prometheus alerting rules (merged per domain)

This keeps 100+ dashboards consistent: identical templating, units, thresholds,
legends and **datasource handling** (panels reference `${DS_PROMETHEUS}` /
`${DS_LOKI}`, never a hardcoded datasource). The category is the spec's folder, the
slug is its filename. Start from [`tools/specs/linux/cpu.yaml`](../tools/specs/linux/cpu.yaml).

## Spec structure

```yaml
uid: <kebab-case, globally unique, <=40 chars>   # e.g. kubernetes-apiserver
title: <Human / Title>                            # e.g. "Kubernetes / API Server"
description: >-                                    # one or two sentences
  What operational question this answers.
datasource: prometheus            # or loki
tags: [domain, subsystem, exporter]
seo_phrase: <one primary search phrase>           # e.g. "etcd Grafana dashboard"
refresh: 30s
time_from: now-6h

questions:                        # 3-5 — these drive the screenshot annotations
  - "Which ... right now?"
production_lessons: >-            # 2-4 sentences: why this dashboard exists in prod
  ...
data_sources:                     # required exporters / metric families
  - "`kube-state-metrics` and `cAdvisor` ..."

templating:                       # template variables (besides the datasource)
  - name: cluster
    label: Cluster
    query: label_values(kube_node_info, cluster)
    description: ...
    multi: false
    includeAll: false

rows:                             # logical sections -> Grafana rows
  - title: <section title — lead with the most important signal>
    panels:
      - type: stat | gauge | bargauge | timeseries | table | heatmap | piechart | state-timeline | logs | text
        title: ...
        description: ...          # shows as the panel info tooltip
        unit: percent             # ALWAYS set a meaningful unit on value panels
        min: 0
        max: 100                  # optional
        width: 6                  # grid columns out of 24 (optional; auto otherwise)
        height: 8                 # grid rows (optional; 8 default)
        thresholds:
          - {color: green, value: null}
          - {color: yellow, value: 75}
          - {color: red, value: 90}
        targets:
          - expr: <PromQL>
            legend: "{{instance}}"     # MUST be quoted if it starts with {{
            instant: true              # for stat/gauge/table single values

alerts:                           # compiled into alerts/<domain>.rules.yml AND the doc
  - name: CamelCaseAlertName
    severity: warning | critical | info
    expr: <PromQL that evaluates to a boolean>
    for: 10m
    summary: "Short templated summary with {{ $labels.x }}"
    why: Why it matters.
    investigate: What to open / check first.
    runbook: Concrete remediation steps.
    recovery: When/how it clears.
    false_positives: Known benign causes.

troubleshooting:                  # optional table
  - {symptom: ..., cause: ..., action: ...}

performance: >-                   # optional; sensible default is generated otherwise
  ...
customization: >-                 # optional
  ...
```

## Panel types and key options

| type | use for | important options |
|------|---------|-------------------|
| `stat` | one headline number | `unit`, `colorMode` (value/background), `calc`, `thresholds`, `instant: true` |
| `gauge` | a value against a known max | `unit`, `min`, `max`, `thresholds` |
| `bargauge` | ranked list (top-N) | `unit`, `orientation`, `displayMode` |
| `timeseries` | trends over time | `unit`, `stacking` (none/normal), `fillOpacity`, `legend` (list/table/hidden), `drawStyle` (line/bars) |
| `table` | per-object detail | `transformations`, `sortBy`, `filterable` |
| `heatmap` | distributions / histograms | `unit` (y-axis) |
| `piechart` | share of a whole | `pieType` (pie/donut) |
| `state-timeline` | up/down / status over time | `mappings`, `thresholds` |
| `logs` | Loki log lines | `datasource: loki`, `sortOrder` |
| `text` | section notes (no query) | `content` (markdown) |

## Design rules (non-negotiable)

1. **Answer a question, don't dump metrics.** The first row must surface the
   headline health signal (saturation, error rate, capacity headroom) so an
   on-call engineer knows in five seconds whether to dig in.
2. **Every value panel has a meaningful `unit`.** Use Grafana unit ids: `percent`
   (0-100), `percentunit` (0-1), `bytes`, `decbytes`, `bytes/sec` = `Bps`,
   `s`, `ms`, `ops`, `reqps`, `short`, `none`, `dtdurations` = `s`.
3. **Thresholds encode operational meaning** — green good, yellow investigate, red
   act. Don't add thresholds you can't justify.
4. **PromQL must be correct and efficient.** Use real metric names from the named
   exporter. Rate windows ≥ `4 ×` scrape interval (use `[5m]`). Aggregate with
   `by (...)` to bound series. Guard instant stats that may be empty with
   `... or vector(0)`.
5. **No URLs, no datasource UIDs, no credentials, no `devopsaitoolkit` anywhere in
   a spec's panel/target content.** Promo links are added by the generator to the
   docs "Related resources" footer only — never in dashboard JSON.

## YAML gotchas (these break the build)

- A scalar that **starts with `{`** is parsed as a flow map. Legends like
  `{{instance}}` **must be quoted**: `legend: "{{instance}}"`.
- A value that **starts with a quote** (`"Cores" is...`) breaks parsing — rephrase
  or wrap the whole value in single quotes.
- Use `>-` for multi-line PromQL; keep indentation consistent.
- `uid` must be unique across the whole repo and match `^[a-z0-9-]{2,40}$`.

## Build and validate locally

```bash
make build        # compile all specs
make validate     # strict checks (schema, units, datasource templating, no URLs)
```

Both must pass with zero errors before you open a PR.
