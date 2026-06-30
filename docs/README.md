# Documentation

Everything you need to deploy, use, customise and contribute dashboards.

## Start here

- **[Dashboard catalog](./catalog.md)** — the full list of dashboards (generated)
- **[Compatibility matrix](./compatibility-matrix.md)** — datasource/exporter needs
- **[Prometheus setup](./prometheus-setup.md)** — exporters, scrape config, rules
- **[Provisioning & importing](./provisioning.md)** — UI, API, file provisioning, k8s

## Using the dashboards

- **[Template variables](./variables.md)** — scope from fleet to a single host
- **[Annotations](./annotations.md)** — overlay deploys, restarts and alerts
- **[Transformations](./transformations.md)** — tables, joins and computed fields
- **[Alerting](./alerting.md)** — deploy the recommended alert rules
- **[Troubleshooting flowchart](./troubleshooting-flowchart.md)** — no-data + incident triage

## Going deeper

- **[Dashboard design principles](./dashboard-design.md)** — why they look the way they do
- **[Performance & efficient PromQL](./performance.md)** — keep dashboards fast
- **[PromQL cookbook](../promql/)** — 90+ explained queries
- **[Observability learning path](./learning-path.md)** — foundations → SLOs → scale
- **[Folder organization](./folder-organization.md)** — repo layout ↔ Grafana folders

## Contributing

- **[Authoring specs](./authoring-specs.md)** — the spec format (how dashboards are built)
- **[CONTRIBUTING](../CONTRIBUTING.md)** — workflow, local checks, PR checklist

## Per-dashboard docs

Each dashboard has its own page under [`docs/dashboards/`](./dashboards/), generated
from its spec — questions answered, panels, data sources, import, alerts,
troubleshooting, performance and customization.
