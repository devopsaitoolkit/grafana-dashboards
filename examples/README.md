# Examples

A runnable, end-to-end stack so you can click through these dashboards in five
minutes — no existing monitoring required.

## Local stack (Docker Compose)

```bash
cd examples
docker compose up -d
# Grafana:     http://localhost:3000   (admin / admin)
# Prometheus:  http://localhost:9090
```

It starts:

- **Prometheus** scraping itself, **node_exporter** and **cAdvisor**, with the
  repo's [recording rules](../recording-rules/) and [alert rules](../alerts/) loaded;
- **Grafana** that auto-provisions the Prometheus datasource (as `DS_PROMETHEUS`) and
  **every dashboard** in [`../dashboards/`](../dashboards/), arranged into folders.

Open Grafana → Dashboards. The `linux/`, `node-exporter/`, `cadvisor/` and `docker/`
boards have live data immediately; the rest light up as you point Prometheus at the
matching exporters (see [docs/prometheus-setup.md](../docs/prometheus-setup.md)).

```bash
docker compose down -v   # tear everything down
```

## Provisioning files

- [`provisioning/prometheus.yml`](./provisioning/prometheus.yml) — scrape config + rules
- [`provisioning/grafana-datasources.yml`](./provisioning/grafana-datasources.yml) — datasource (uid `DS_PROMETHEUS`)
- [`provisioning/grafana-dashboards.yml`](./provisioning/grafana-dashboards.yml) — file provider for `../dashboards`

These are the same patterns documented in [docs/provisioning.md](../docs/provisioning.md);
adapt them for your real Grafana/Prometheus deployment.

## Importing just one dashboard

Prefer not to run the stack? Import a single JSON:

```bash
export GRAFANA_URL=http://localhost:3000 GRAFANA_TOKEN=glsa_xxx
../scripts/import-dashboard.sh ../dashboards/linux/cpu.json
```
