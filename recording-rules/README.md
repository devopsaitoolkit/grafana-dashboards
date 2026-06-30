# Recording rules

Precomputed expressions that make large-fleet dashboards render instantly and keep
alert evaluation cheap. Each rule follows Prometheus's `level:metric:operation`
naming convention so its meaning is obvious at the call site.

## Files

| File | For | Example rule |
|------|-----|--------------|
| `node.rules.yml` | Linux / node_exporter | `instance:node_cpu_utilisation:rate5m` |
| `kubernetes.rules.yml` | Kubernetes | `cluster:node_cpu_requests_commitment:ratio` |

## Loading them

**Prometheus** — reference the files in `prometheus.yml`:

```yaml
rule_files:
  - /etc/prometheus/rules/node.rules.yml
  - /etc/prometheus/rules/kubernetes.rules.yml
```

Reload Prometheus (`SIGHUP` or `POST /-/reload`) and verify with
`promtool check rules recording-rules/*.yml`.

**Mimir / VictoriaMetrics** — load the same files through the respective ruler.

## When to use them

A dashboard panel that aggregates a high-cardinality metric (`container_*`,
`node_*` across thousands of series) over a wide time range can be slow. Swap the
raw expression for the recording rule: the dashboards' **Performance** sections
name the specific rule to use. Recording rules are evaluated once per interval,
not once per dashboard view, so the cost is paid once for everyone.
