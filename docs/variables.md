# Template variables

Variables turn one dashboard into a tool for the whole fleet. Every dashboard here
is templated so you can scope from "all hosts" down to a single instance without
editing anything.

## The variables you'll see

| Variable | Typical query | Purpose |
|----------|---------------|---------|
| `$job` | `label_values(up, job)` | Pick the scrape job (which exporter/fleet) |
| `$instance` | `label_values(node_uname_info{job="$job"}, instance)` | One or many hosts (multi-select) |
| `$cluster` | `label_values(kube_node_info, cluster)` | Kubernetes cluster |
| `$namespace` | `label_values(kube_pod_info{cluster="$cluster"}, namespace)` | Kubernetes namespace |
| `$node` / `$hypervisor` | `label_values(...)` | A single node / compute host |
| `$interval` | built-in interval | Smooth rates on wide time ranges |

## Chained (cascading) variables

Variables reference each other so the choices stay consistent: `$instance` is
queried *within* the selected `$job`, `$namespace` within the selected `$cluster`.
Change the parent and the children re-query automatically.

```text
$job ─▶ $instance        # instance list depends on the chosen job
$cluster ─▶ $namespace ─▶ $workload
```

## Multi-value and "All"

Most scoping variables enable **multi-select** and **Include All**. In PromQL these
become regex matches, so always match with `=~`:

```promql
rate(node_cpu_seconds_total{job="$job", instance=~"$instance"}[5m])
```

The `All` value is configured as `.*` so it matches everything. Using `=` instead of
`=~` with a multi-value variable is a common cause of "No data".

## Adding a variable to a spec

```yaml
templating:
  - name: namespace
    label: Namespace
    query: label_values(kube_pod_info{cluster="$cluster"}, namespace)
    description: Kubernetes namespace to scope to.
    multi: true
    includeAll: true
```

Supported `type`s: `query` (default), `custom`, `interval`, `constant`, `textbox`.
See [authoring-specs.md](./authoring-specs.md) for all options. After editing, run
`make build` to regenerate.

## The `$interval` trick

For panels rendered over very wide ranges, use a rate window tied to `$__rate_interval`
(Grafana computes it from the panel width and scrape interval) so the graph stays
smooth without manual tuning:

```promql
rate(http_requests_total{job="$job"}[$__rate_interval])
```

The dashboards use fixed `5m` windows by default for predictability; switch to
`$__rate_interval` when you frequently zoom across hours-to-weeks.
