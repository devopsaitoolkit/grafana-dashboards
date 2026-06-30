# Provisioning & importing

Three ways to get these dashboards into Grafana, from quickest to most automated.

## 1. Import a single dashboard (UI)

*Dashboards → New → Import →* upload a JSON file from `dashboards/` (or paste it),
then **select your datasource** when prompted. Done. The datasource prompt appears
because dashboards reference `${DS_PROMETHEUS}` / `${DS_LOKI}` inputs rather than a
fixed datasource.

## 2. Import via the API (scriptable)

```bash
export GRAFANA_URL=https://grafana.example.com
export GRAFANA_TOKEN=glsa_xxx          # Administration → Service accounts → token

scripts/import-dashboard.sh dashboards/linux/cpu.json
# or a whole folder:
find dashboards/kubernetes -name '*.json' -print0 | xargs -0 scripts/import-dashboard.sh
```

`import-dashboard.sh` resolves the datasource inputs to your named Grafana
datasources (`Prometheus` / `Loki` by default; override with `DS_PROMETHEUS_NAME`).

## 3. File-based provisioning (GitOps)

Best for managing the whole library as code. The folder structure under
`dashboards/` becomes nested Grafana folders.

```bash
scripts/provision.sh /var/lib/grafana/dashboards
```

That copies the JSON and prints the provider config to install at
`/etc/grafana/provisioning/dashboards/devopsaitoolkit.yaml`:

```yaml
apiVersion: 1
providers:
  - name: devopsaitoolkit
    type: file
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: true
```

Pair it with [datasource provisioning](../datasources/) so the `${DS_*}` inputs bind
automatically by UID — no manual datasource selection for provisioned dashboards.

### Kubernetes (sidecar)

If you run the Grafana Helm chart with the dashboard sidecar, label a ConfigMap per
dashboard:

```bash
kubectl create configmap linux-cpu \
  --from-file=dashboards/linux/cpu.json -n monitoring
kubectl label configmap linux-cpu grafana_dashboard=1 -n monitoring
```

The sidecar imports any ConfigMap carrying the `grafana_dashboard=1` label.

## Verifying

After import, open the dashboard and confirm panels render. If they show **No data**,
check the datasource binding and that the relevant exporter's `job` label matches the
dashboard's `$job` variable. See each dashboard's **Troubleshooting** section.
