# Datasource provisioning

Grafana datasource definitions that pair with the dashboards in this repo. Drop
the YAML files into `/etc/grafana/provisioning/datasources/` (or mount them in a
container) and Grafana will create the datasources on start.

## How the UIDs line up

Every dashboard references its datasource by an **input** — `${DS_PROMETHEUS}` or
`${DS_LOKI}` — instead of a hardcoded UID. When you provision a datasource with the
matching `uid` (e.g. `DS_PROMETHEUS`), [provisioned dashboards](../docs/provisioning.md)
bind to it automatically with no manual selection.

| File | Datasource | `uid` | Notes |
|------|------------|-------|-------|
| `prometheus.yaml` | Prometheus | `DS_PROMETHEUS` | Default metrics backend |
| `victoriametrics.yaml` | VictoriaMetrics | `DS_PROMETHEUS` | Drop-in Prometheus replacement |
| `mimir.yaml` | Grafana Mimir | `DS_PROMETHEUS` | Multi-tenant; set `X-Scope-OrgID` |
| `loki.yaml` | Loki | `DS_LOKI` | Logs (for the Loki-backed dashboards) |
| `tempo.yaml` | Tempo | `DS_TEMPO` | Traces; enables exemplar correlation |

Use **one** of Prometheus / VictoriaMetrics / Mimir as `DS_PROMETHEUS` — they are
API-compatible and the dashboards use standard PromQL that runs on all three.

## Secrets

These files contain **no credentials**. Where a tenant id or token is needed (e.g.
Mimir's `X-Scope-OrgID`), set it via `secureJsonData` at deploy time or with
environment substitution — never commit real values.
