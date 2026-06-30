# Kubernetes (kube-state-metrics + cAdvisor)

Cluster-level questions answered with `kube-state-metrics` (object state: `kube_*`) and
cAdvisor (runtime usage: `container_*`). The recurring theme is joining usage to
declared spec — usage means little without the request, limit, or allocatable it's
measured against. Adjust `namespace`/`cluster` matchers to your environment.

## 1. Pod container restarts in the last hour

```promql
increase(kube_pod_container_status_restarts_total[1h]) > 0
```

**Purpose:** Which containers have restarted recently — the first thing to check during an
incident.

**How it works:** The restart counter only ever increases, so `increase(...[1h])` counts
restarts in the window; `> 0` keeps only containers that actually restarted. Pairs with
`kube_pod_container_status_last_terminated_reason` to see *why* (OOMKilled, Error).

**Expected output:** Instant vector, restart count, one series per restarting container.

**Common modifications:**

- `sum by (namespace) (increase(...[1h]))` for a per-namespace restart total.
- Join `kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} == 1` to isolate OOM kills.

**Performance:** Cheap. For exact counts over long windows, `… - … offset 1h` avoids
`increase()`'s extrapolation rounding.

## 2. CrashLooping pods

```promql
rate(kube_pod_container_status_restarts_total[15m]) * 60 * 15 > 3
```

**Purpose:** Pods restarting repeatedly — a crash loop, not a one-off restart.

**How it works:** `rate(...[15m]) × 900` reconstructs the approximate restart count over 15
minutes from the per-second rate; `> 3` flags more than three restarts in that window. Using
a rate (rather than raw `increase`) makes the signal smooth enough for an alert with
`for: 5m`.

**Expected output:** Instant vector, restarts-per-15m, only for crash-looping containers.

**Common modifications:**

- Use `increase(...[15m]) > 3` for the same idea with exact-ish counts.
- Add `kube_pod_status_phase{phase="Running"} == 1` joins to ignore pods you've already deleted.

**Performance:** Cheap. The classic kube-prometheus `KubePodCrashLooping` alert is this
shape.

## 3. CPU throttling ratio

```promql
sum by (namespace, pod) (rate(container_cpu_cfs_throttled_periods_total[5m]))
  /
sum by (namespace, pod) (rate(container_cpu_cfs_periods_total[5m]))
```

**Purpose:** What fraction of CFS scheduling periods a pod was throttled — the signal that
a CPU **limit** is too low.

**How it works:** `cfs_periods_total` counts every CPU enforcement period; `cfs_throttled_
periods_total` counts those in which the container hit its limit and was throttled. The
ratio (0–1) is the throttling rate. High throttling with low CPU usage is the textbook
"limit set too aggressively" symptom — latency suffers even though the dashboard shows
spare CPU.

**Expected output:** Instant vector, 0–1, one series per pod. Above ~0.25 sustained is
worth investigating.

**Common modifications:**

- `* 100` for percent.
- Add `container` to the grouping to find which container in the pod is throttled.

**Performance:** cAdvisor series are numerous; scope with a `namespace` matcher. `[5m]` is
the safe window.

## 4. Container CPU usage vs its request

```promql
sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{image!=""}[5m]))
  /
sum by (namespace, pod) (kube_pod_container_resource_requests{resource="cpu"})
```

**Purpose:** How a pod's actual CPU compares to what it requested — over 1 means it's
borrowing idle capacity; well under 1 means it's over-requested and wasting schedulable room.

**How it works:** The numerator is real CPU cores used (`image!=""` drops the pod-level
pause/cgroup roll-up series so containers aren't double-counted). The denominator is the
summed CPU request. Both aggregate to `(namespace, pod)` so the division matches.

**Expected output:** Instant vector, ratio, one series per pod.

**Common modifications:**

- Swap `requests` → `limits` for headroom-to-limit.
- `resource="memory"` with `container_memory_working_set_bytes` for the memory equivalent.

**Performance:** A common over/under-provisioning panel. The `image!=""` filter is
essential — without it you double-count the cgroup total.

## 5. Container memory vs limit (OOM risk)

```promql
sum by (namespace, pod) (container_memory_working_set_bytes{image!=""})
  /
sum by (namespace, pod) (kube_pod_container_resource_limits{resource="memory"})
```

**Purpose:** How close a pod is to its memory limit — approaching 1 means an imminent
OOMKill.

**How it works:** `container_memory_working_set_bytes` is the figure the kernel's OOM
killer actually watches (RSS + active page cache that can't be reclaimed), which is why it's
the right numerator — not `usage_bytes`, which includes reclaimable cache. Dividing by the
memory limit gives the danger ratio.

**Expected output:** Instant vector, 0–1, one series per pod. `> 0.9` sustained predicts an
OOMKill.

**Common modifications:**

- Replace `limits` with `requests` to judge scheduling pressure instead of OOM risk.
- `topk(10, …)` to find the pods closest to their limit cluster-wide.

**Performance:** Working-set is a gauge — no rate, cheap. Keep the `image!=""` filter.

## 6. Pods by phase

```promql
sum by (phase) (kube_pod_status_phase)
```

**Purpose:** Cluster-wide pod state — how many Running, Pending, Failed, Succeeded,
Unknown.

**How it works:** `kube_pod_status_phase` is a constant-`1` series with a `phase` label per
pod (only the current phase is `1`). Summing `by (phase)` counts pods in each state. A
growing `Pending` count usually means scheduling pressure or unschedulable resource
requests.

**Expected output:** Instant vector, integer counts, one series per phase.

**Common modifications:**

- Add `namespace` to the grouping for per-namespace state.
- `kube_pod_status_phase{phase="Pending"} == 1` joined with age to find stuck pods.

**Performance:** Cheap. A staple of cluster-overview dashboards.

## 7. CPU requests committed vs allocatable

```promql
sum(kube_pod_container_resource_requests{resource="cpu"})
  /
sum(kube_node_status_allocatable{resource="cpu"})
```

**Purpose:** What fraction of the cluster's schedulable CPU is already promised to pods —
the scheduler's commitment ratio.

**How it works:** Total CPU **requests** over total node **allocatable** (capacity minus
kube/system reservations). At 1.0 the scheduler can't place another pod that requests CPU,
regardless of actual usage. This is about *bookings*, not utilisation — a cluster can be
100% committed and 20% utilised.

**Expected output:** Instant vector, 0–1 (or slightly above if overcommitted via limits).

**Common modifications:**

- Add `by (node)` to both sides for per-node commitment and bin-packing skew.
- `resource="memory"` for the memory equivalent.

**Performance:** Cheap. See [capacity-and-saturation.md](./capacity-and-saturation.md) for
overcommit ratios built on this.

## 8. PersistentVolumeClaim fill percentage

```promql
100 * (
  1 - kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes
)
```

**Purpose:** Percent full per PVC — stateful workloads fail hard when volumes fill.

**How it works:** The kubelet exposes per-PVC `available` and `capacity` bytes;
`1 - avail/capacity` is the used fraction, `× 100` percent. These series carry
`persistentvolumeclaim` and `namespace` labels so you can map a full volume straight to a
workload.

**Expected output:** Instant vector, 0–100, one series per PVC.

**Common modifications:**

- `predict_linear(kubelet_volume_stats_available_bytes[6h], 24*3600) < 0` to forecast which PVCs fill within a day.
- `topk(10, …)` for the fullest volumes.

**Performance:** Cheap. The prediction variant loads 6h per PVC — fine for a handful of
volumes.

## 9. API server error ratio

```promql
sum(rate(apiserver_request_total{code=~"5.."}[5m]))
  /
sum(rate(apiserver_request_total[5m]))
```

**Purpose:** Fraction of API-server requests failing with 5xx — control-plane health.

**How it works:** Standard error-ratio shape: 5xx rate over total rate. A rising value
means the API server (or its etcd backend) is struggling, which cascades into controllers,
the scheduler, and kubelets. Note `apiserver_request_total` (the request counter) is
distinct from `apiserver_request_duration_seconds_*` (the latency histogram).

**Expected output:** Instant vector, 0–1, normally near 0.

**Common modifications:**

- Add `by (verb, resource)` to find which operations fail (e.g. `LIST pods`).
- Exclude expected `409` conflicts by matching `code=~"5.."` only, as shown.

**Performance:** Cheap. Pair with the latency query below for a full control-plane SLI.

## 10. API server read latency (p99)

```promql
histogram_quantile(0.99,
  sum by (le) (rate(apiserver_request_duration_seconds_bucket{verb=~"GET|LIST"}[5m]))
)
```

**Purpose:** p99 latency of API-server read requests — the number that governs how snappy
`kubectl` and controllers feel.

**How it works:** The canonical histogram pattern (`rate` the `_bucket`, `sum by (le)`,
then `histogram_quantile`), scoped to read verbs. `LIST` of large collections is the usual
culprit for tail latency and is worth isolating from cheap `GET`s.

**Expected output:** Instant vector, seconds, one series. Healthy clusters sit in the tens
of ms for `GET`, higher for big `LIST`s.

**Common modifications:**

- `sum by (le, resource)` to find which resource type is slow.
- `verb="WATCH"` excluded deliberately — watches are long-lived and skew the tail.

**Performance:** Bucket-heavy; `sum by (le)` collapses instances first. Record it if it
drives a dashboard. See [histograms-and-latency.md](./histograms-and-latency.md).

## 11. Nodes not Ready

```promql
kube_node_status_condition{condition="Ready", status="true"} == 0
```

**Purpose:** Nodes currently failing the Ready condition — capacity that's silently gone.

**How it works:** `kube_node_status_condition` emits a series per (condition, status)
combination valued `1` when that combination holds. Selecting `condition="Ready",
status="true"` and testing `== 0` returns nodes whose Ready=true is *not* asserted — i.e.
NotReady or Unknown nodes.

**Expected output:** Empty when the cluster is healthy; one series per unhealthy node.

**Common modifications:**

- `condition="MemoryPressure", status="true" == 1` to catch nodes under memory pressure.
- `count(kube_node_status_condition{condition="Ready",status="true"} == 1)` for the Ready node count.

**Performance:** Cheap. Alert with `for: 5m` to ride out brief kubelet heartbeat gaps.

## 12. Deployment replica mismatch

```promql
kube_deployment_spec_replicas
  - kube_deployment_status_replicas_available
  > 0
```

**Purpose:** Deployments running fewer available replicas than desired — a degraded rollout
or scheduling failure.

**How it works:** `spec_replicas` is the declared count, `status_replicas_available` the
number passing readiness. A positive difference means missing replicas. Both series share
`deployment`/`namespace` labels so the subtraction matches directly without `on()`.

**Expected output:** Instant vector, missing-replica count, only for degraded Deployments.

**Common modifications:**

- `kube_statefulset_status_replicas_ready < kube_statefulset_replicas` for StatefulSets.
- Add `for: 15m` in an alert to ignore normal rollout churn.

**Performance:** Cheap. The `> 0` filter keeps the result set to only the Deployments that
matter.

## 13. Pods stuck Pending too long

```promql
kube_pod_status_phase{phase="Pending"} == 1
  and on(namespace, pod)
(time() - kube_pod_start_time > 600)
```

**Purpose:** Pods that have been Pending for more than 10 minutes — unschedulable due to
insufficient resources, node selectors, or unbound PVCs.

**How it works:** `kube_pod_status_phase{phase="Pending"} == 1` selects currently-Pending
pods; `time() - kube_pod_start_time` is each pod's age in seconds. The `and on(namespace,
pod)` keeps only pods that are both Pending and older than 600s, filtering out normal
just-scheduled churn. Long-Pending pods almost always mean the scheduler can't satisfy the
request.

**Expected output:** Empty when healthy; one series per stuck pod.

**Common modifications:**

- Join `kube_pod_status_unschedulable == 1` to confirm the scheduler gave up.
- Raise the threshold to `1800` for batch/CI namespaces that queue intentionally.

**Performance:** Cheap. The `on(namespace, pod)` label set must match on both sides.
