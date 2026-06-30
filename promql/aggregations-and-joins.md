# Aggregations and joins

Aggregation collapses many series into a summary; joining combines two metrics that
share some labels. Getting label matching right is the single most common source of
"no data" and "many-to-many matching" errors, so this page is mostly about labels.

## 1. topk and bottomk — the worst N offenders

```promql
topk(10, sum by (pod) (rate(container_cpu_usage_seconds_total{image!=""}[5m])))
```

**Purpose:** The ten pods burning the most CPU right now.

**How it works:** The inner `sum by (pod)` gives per-pod CPU cores. `topk(10, …)` keeps
the ten series with the highest values and drops the rest, preserving their labels.
`bottomk` keeps the lowest. Unlike `max`, `topk` returns the **series** (so you see
which pod), not just the value.

**Expected output:** Instant vector, up to 10 series, unit CPU cores (per second of CPU
time per second).

**Common modifications:**

- `bottomk(5, node_filesystem_avail_bytes{mountpoint="/"})` for the fullest disks.
- `topk(20, count by (__name__)({__name__=~".+"}))` to find high-cardinality metrics.

**Performance:** `topk` must rank every input series, so the cost is in the inner query,
not the `topk`. Don't use `topk` inside alert rules — the result set changes shape every
evaluation and confuses `for:` and Alertmanager grouping.

## 2. quantile aggregation across instances

```promql
quantile by (job) (0.95, node_load1)
```

**Purpose:** The 95th-percentile 1-minute load across all hosts of each job — a fleet
distribution, not a histogram.

**How it works:** `quantile(φ, …)` is an **aggregation operator** that computes the φ
quantile across the *current set of series* (one value per host here), grouped `by (job)`.
This is the right tool for "the p95 host", and is different from `histogram_quantile`,
which estimates a quantile from bucket counts within one metric.

**Expected output:** Instant vector, one series per job, same unit as the gauge.

**Common modifications:**

- `quantile(0.5, …)` for the median host.
- `count_values("v", round(node_load1))` to build a histogram of load values.

**Performance:** Cheap relative to histogram math, but only as meaningful as the number
of input series — a p95 across three hosts is noisy.

## 3. avg, max, stddev together for a fleet view

```promql
max by (job) (node_filesystem_avail_bytes{mountpoint="/"})
  /
avg by (job) (node_filesystem_size_bytes{mountpoint="/"})
```

**Purpose:** Compare the best-case free space to the average disk size, a quick skew check.

**How it works:** Two aggregations grouped on the same label set (`job`) divide cleanly
because their output labels match exactly. Mixing `max by (job)` and `avg by (job)` is
safe; mixing `max by (job)` with `avg by (instance)` would not match.

**Expected output:** Instant vector, dimensionless ratio, one series per job.

**Common modifications:**

- `stddev by (job) (node_load1)` to quantify how uneven a fleet's load is.
- `max - avg` instead of a ratio to express absolute skew.

**Performance:** Negligible. Keep both sides aggregated to the **same** label set or the
division returns empty.

## 4. One-to-one vector matching with ignoring()

```promql
rate(node_disk_written_bytes_total[5m])
  /
ignoring(direction) rate(node_disk_writes_completed_total[5m])
```

**Purpose:** Average bytes per write operation — disk write size.

**How it works:** The two metrics share `instance`, `device`, and `job`, so by default
they match one-to-one. `ignoring(direction)` is shown here as the pattern for dropping a
label that exists on only one side; for these two metrics the labels already align, and
`ignoring()`/`on()` is how you reconcile any stray label so the element-wise division
finds its partner.

**Expected output:** Instant vector, bytes per operation, one series per `(instance,
device)`.

**Common modifications:**

- `on(instance, device)` instead of `ignoring(...)` to match on an explicit allow-list.
- Guard the denominator with `> 0` to skip idle disks (avoids `NaN`).

**Performance:** Vector matching is cheap once cardinality is reasonable. "Many-to-many
matching not allowed" means duplicate label sets on one side — fix with `on()`/`ignoring()`
or aggregate first.

## 5. group_left to enrich a metric with kube_pod_info

```promql
sum by (node) (
  sum by (pod, namespace) (rate(container_cpu_usage_seconds_total{image!=""}[5m]))
  * on(pod, namespace) group_left(node)
  kube_pod_info
)
```

**Purpose:** Roll up per-pod CPU usage onto the **node** it runs on, using
`kube_pod_info` only to supply the `node` label.

**How it works:** cAdvisor's CPU metric has no `node` label, but `kube_pod_info` does.
`* on(pod, namespace) group_left(node)` is a **many-to-one** join: many CPU series match
the single matching `kube_pod_info` row per `(pod, namespace)`, and `group_left(node)`
copies the `node` label from the right side onto the result. Multiplying by the constant
`1` of `kube_pod_info` is the standard "join to add a label" trick. The outer
`sum by (node)` then aggregates per node.

**Expected output:** Instant vector, CPU cores, one series per node.

**Common modifications:**

- `group_left(workload)` against `namespace_workload_pod:kube_pod_owner:relabel` to attribute usage to a Deployment.
- Swap to `group_right(...)` when the "one" side is on the left.

**Performance:** This is the workhorse Kubernetes join. Keep the inner expression
aggregated to `(pod, namespace)` first so the join cardinality stays small.

## 6. group_left to carry node role / label metadata

```promql
sum by (label_topology_kubernetes_io_zone) (
  node_memory_MemTotal_bytes
  * on(instance) group_left(node)
  label_replace(kube_node_info, "instance", "$1", "internal_ip", "(.*)")
  * on(node) group_left(label_topology_kubernetes_io_zone)
  kube_node_labels
)
```

**Purpose:** Total physical memory per availability zone, joining node-exporter to
Kubernetes node labels.

**How it works:** Two chained `group_left` joins. The first maps node-exporter's
`instance` to the Kubernetes `node` name via `kube_node_info` (after `label_replace`
manufactures a matching `instance` label). The second pulls the
`label_topology_kubernetes_io_zone` label off `kube_node_labels`. The final
`sum by (...zone)` aggregates per zone.

**Expected output:** Instant vector, bytes, one series per zone.

**Common modifications:**

- Replace the zone label with `label_node_role_kubernetes_io_control_plane` to split control plane from workers.
- Use the same pattern with `node_filesystem_size_bytes` for capacity per zone.

**Performance:** Chained joins multiply matching work; pre-aggregate and keep matchers
tight. A recording rule is justified if this drives a dashboard.

## 7. label_replace to manufacture a join key

```promql
label_replace(
  node_uname_info,
  "host", "$1", "nodename", "([^.]+)\\..*"
)
```

**Purpose:** Add a short `host` label (the hostname without its domain) so this metric
can join to others keyed on short names.

**How it works:** `label_replace(v, dst, repl, src, regex)` applies `regex` to the value
of label `src`; if it matches, it writes `repl` (with `$1`, `$2` capture groups) into a
**new or overwritten** label `dst`. Series that don't match pass through unchanged. It's
the standard way to reshape labels for a join without changing the source data.

**Expected output:** Instant vector identical to `node_uname_info` but with an added
`host` label.

**Common modifications:**

- `label_replace(up, "team", "platform", "namespace", "kube-system")` to tag series.
- Use `label_join` to concatenate several labels into one composite key.

**Performance:** Cheap per series but runs on every input — avoid wrapping a giant
`{__name__=~".+"}` selector in it.

## 8. count by to find label distribution

```promql
count by (status_class) (
  label_replace(
    rate(nginx_ingress_controller_requests[5m]) > 0,
    "status_class", "${1}xx", "status", "([0-9])[0-9][0-9]"
  )
)
```

**Purpose:** How many distinct ingress series are currently serving each status class
(2xx/3xx/4xx/5xx).

**How it works:** `label_replace` collapses the three-digit `status` into a one-character
class with a capture group, and `count by (status_class)` counts the resulting series.
The `> 0` filter keeps only active series so idle endpoints don't inflate the count.

**Expected output:** Instant vector, integer count, one series per status class.

**Common modifications:**

- Swap `count` for `sum` to get request rate per class instead of series count.
- Add `, ingress` to the `by(...)` to break the count down per ingress object.

**Performance:** The `rate(...) > 0` filter is what controls cost; ingress controllers
can emit very high-cardinality path/status series.

## 9. Many-to-one ratio: errors per deployment

```promql
sum by (deployment) (
  rate(http_requests_total{code=~"5.."}[5m])
  * on(pod) group_left(deployment)
  label_replace(kube_pod_owner{owner_kind="ReplicaSet"}, "deployment", "$1", "owner_name", "(.*)-[^-]+")
)
/
sum by (deployment) (
  rate(http_requests_total[5m])
  * on(pod) group_left(deployment)
  label_replace(kube_pod_owner{owner_kind="ReplicaSet"}, "deployment", "$1", "owner_name", "(.*)-[^-]+")
)
```

**Purpose:** 5xx error ratio attributed to each Deployment, by mapping pod → ReplicaSet →
Deployment name.

**How it works:** `kube_pod_owner` links a pod to its ReplicaSet; stripping the trailing
hash from the ReplicaSet name with `label_replace` recovers the Deployment name. Both
numerator and denominator perform the **same** join so their `deployment` labels match
for the final division.

**Expected output:** Instant vector, ratio 0–1, one series per deployment.

**Common modifications:**

- Multiply by 100 for a percentage.
- Use the official `namespace_workload_pod:kube_pod_owner:relabel` recording rule instead of the regex if your kube-prometheus-stack ships it.

**Performance:** Doing the join twice is wasteful — record the joined per-pod request
rates once, then divide the recorded series.

## 10. and / unless / or for set operations

```promql
(rate(node_network_receive_bytes_total[5m]) > 1e8)
  and on(instance)
(node_load1 > count by (instance) (node_cpu_seconds_total{mode="idle"}))
```

**Purpose:** Hosts that are **both** receiving heavy network traffic **and** CPU-saturated
(load above core count) — correlated saturation.

**How it works:** `and` is a set intersection: it returns left-hand series only where a
matching series exists on the right. `on(instance)` scopes the match to the host. `unless`
is the inverse (left minus right) and `or` is the union. These operators filter by
presence; they don't do arithmetic.

**Expected output:** Instant vector, network bytes/sec, only for hosts meeting both
conditions (often empty — that's healthy).

**Common modifications:**

- `unless on(instance) (node_systemd_unit_state{name="maintenance.service",state="active"} == 1)` to suppress hosts in maintenance.
- `or` to union two alert conditions into one series set.

**Performance:** Set operators are cheap, but both sides are fully evaluated first. Keep
the heavier side filtered with matchers before combining.
