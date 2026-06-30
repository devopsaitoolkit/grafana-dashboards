# Annotations

Annotations draw context onto your time series — deploys, restarts, alert firings —
so a spike lines up with *what happened*. Every dashboard ships with the built-in
"Annotations & Alerts" layer enabled; here's how to add more.

## Built-in: alerts on the graph

The default annotation layer shows Grafana alert state changes. When an alert tied to
a panel's query fires, a region appears on the graph. Nothing to configure.

## Deploy / change markers from Prometheus

Turn a metric that changes on deploy into annotations. Add an annotation query (in
Grafana: *Dashboard settings → Annotations → New*) of type **Prometheus**:

```promql
# a marker every time a process restarts (new start time)
changes(process_start_time_seconds{job="$job"}[5m]) > 0
```

Use the instance/version labels as the annotation text so each marker says what
restarted. Common sources:

- `kube_deployment_status_observed_generation` changes → rollout markers
- `node_boot_time_seconds` changes → reboot markers
- a `build_info{version=...}` series → version-change markers

## Region annotations from alerts/state

`ALERTS` (Prometheus' synthetic series for firing alerts) makes a great region layer:

```promql
ALERTS{alertstate="firing", severity="critical"}
```

Shade the period a critical alert was firing across every panel.

## From your CI/CD

Post deploy events via the Grafana HTTP API so they appear on every dashboard:

```bash
curl -fsSL -X POST "$GRAFANA_URL/api/annotations" \
  -H "Authorization: Bearer $GRAFANA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tags":["deploy","api"],"text":"Deployed api v1.4.2"}'
```

Tag them (`deploy`, `incident`, `maintenance`) and add a tag-based annotation layer
to filter which show.

## Good practice

- Keep deploy markers on a **dim color** so they don't overwhelm the data.
- Use **tags** consistently so you can toggle classes of annotation on/off.
- Region annotations (start+end) are better than points for incidents and
  maintenance windows.
