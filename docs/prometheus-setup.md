# Prometheus setup

These dashboards expect metrics from standard exporters in a Prometheus-compatible
store (Prometheus, VictoriaMetrics or Mimir). This page gets you from zero to data.

## Minimum scrape config

```yaml
# prometheus.yml
global:
  scrape_interval: 15s          # dashboards assume ≤ 15s; rate windows are 5m
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/rules/*.rules.yml   # alerts/ and recording-rules/ from this repo

scrape_configs:
  - job_name: node                      # Linux dashboards
    static_configs:
      - targets: ["host-a:9100", "host-b:9100"]

  - job_name: cadvisor                  # Docker / container dashboards
    static_configs:
      - targets: ["host-a:8080"]

  - job_name: prometheus                # the Prometheus self-monitoring dashboard
    static_configs:
      - targets: ["localhost:9090"]
```

The dashboards template on the `job` label, so name jobs clearly. The defaults the
variables expect are the conventional ones (`node`, `cadvisor`, `kubernetes-*`,
`openstack-exporter`, `mysqld`, `postgres`, `redis`, …) but every dashboard lets you
pick the job at the top.

## Exporters by dashboard family

| Dashboards | Exporter | Default port |
|------------|----------|--------------|
| `linux/`, `node-exporter/` | [node_exporter](https://github.com/prometheus/node_exporter) | 9100 |
| `docker/`, `cadvisor/` | [cAdvisor](https://github.com/google/cadvisor) | 8080 |
| `kubernetes/` | kube-state-metrics + cAdvisor + kubelet | 8080 / 10250 |
| `openstack/` | [openstack-exporter](https://github.com/openstack-exporter/openstack-exporter) | 9180 |
| `openstack/rabbitmq/` | RabbitMQ Prometheus plugin | 15692 |
| `openstack/mariadb/`, `mysql/` | [mysqld_exporter](https://github.com/prometheus/mysqld_exporter) | 9104 |
| `openstack/haproxy/` | HAProxy native exporter | 8404 |
| `postgres/` | [postgres_exporter](https://github.com/prometheus-community/postgres_exporter) | 9187 |
| `redis/` | [redis_exporter](https://github.com/oliver006/redis_exporter) | 9121 |
| `nginx/` | [nginx-prometheus-exporter](https://github.com/nginxinc/nginx-prometheus-exporter) | 9113 |
| `apache/` | [apache_exporter](https://github.com/Lusitaniae/apache_exporter) | 9117 |
| `prometheus/`, `loki/`, `tempo/`, `mimir/`, `victoria-metrics/` | the components' own `/metrics` | — |
| `vmware/` | [vmware_exporter](https://github.com/pryorda/vmware_exporter) | 9272 |
| `aws/` | [cloudwatch_exporter](https://github.com/prometheus/cloudwatch_exporter) | 9106 |
| `azure/` | [azure-metrics-exporter](https://github.com/webdevops/azure-metrics-exporter) | 8080 |
| `gcp/` | [stackdriver_exporter](https://github.com/prometheus-community/stackdriver_exporter) | 9255 |

Each dashboard's doc page lists the exact metric families it needs under **Data
source requirements**.

## Rules

Load the [alert rules](../alerts/) and [recording rules](../recording-rules/):

```bash
cp alerts/*.rules.yml recording-rules/*.rules.yml /etc/prometheus/rules/
promtool check rules /etc/prometheus/rules/*.rules.yml
curl -X POST http://localhost:9090/-/reload
```

## Then

Provision datasources from [`datasources/`](../datasources/) and import dashboards —
see [provisioning.md](./provisioning.md) and the [catalog](./catalog.md).
