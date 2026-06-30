# Folder organization

How this repository is laid out, and how that maps onto Grafana folders.

## Repository layout

```text
grafana-dashboards/
├── tools/
│   ├── dashgen/         # the generator (panels, layout, docs, svg, validate)
│   └── specs/<cat>/     # SOURCE OF TRUTH — one YAML spec per dashboard
├── dashboards/<cat>/    # generated Grafana JSON (do not hand-edit)
├── docs/
│   ├── dashboards/<cat>/  # generated per-dashboard doc pages
│   └── *.md             # guides (this folder)
├── screenshots/<cat>/   # generated annotated SVG schematics
├── alerts/              # generated Prometheus alert rules (per domain)
├── recording-rules/     # recording rules for large fleets
├── datasources/         # Grafana datasource provisioning examples
├── promql/              # PromQL cookbook
├── examples/            # runnable end-to-end examples
└── scripts/             # import/export/backup/provision helpers
```

`<cat>` is the dashboard category — `linux`, `kubernetes`, `docker`,
`openstack/nova`, `prometheus`, `postgres`, … The **same category path** is used
everywhere (spec → JSON → doc → screenshot), so finding the four artdefacts for any
dashboard is mechanical.

## How it maps into Grafana

With [file provisioning](./provisioning.md) and `foldersFromFilesStructure: true`,
the directory tree under `dashboards/` becomes nested **Grafana folders**:

```text
dashboards/openstack/nova/hypervisor-capacity.json
        └────────────────────────────────────────▶  Grafana: OpenStack / Nova / Hypervisor capacity
```

Recommended Grafana folder structure (mirrors the repo):

- **Linux**, **Kubernetes**, **Docker** — infrastructure layers
- **OpenStack** with sub-folders per service (Nova, Neutron, Cinder, …)
- **Monitoring** — Prometheus, Loki, Tempo, Mimir, VictoriaMetrics
- **Databases** — PostgreSQL, MySQL, Redis
- **Web** — NGINX, Apache
- **Cloud** — VMware, AWS, Azure, GCP

## Tags

Every dashboard carries tags (its domain + the exporters it needs). Use Grafana's
tag filter on the Dashboards page to slice across folders — e.g. show everything
tagged `node-exporter` or `capacity`. The [catalog](./catalog.md) and
[compatibility matrix](./compatibility-matrix.md) list the tags per dashboard.

## Naming

- **uid**: `<category-with-dashes>-<slug>` (e.g. `kubernetes-etcd`), stable across
  re-imports so links and provisioning don't break.
- **title**: `Domain / Subject` (e.g. `OpenStack / Hypervisor capacity`) so the
  Grafana search reads naturally.
