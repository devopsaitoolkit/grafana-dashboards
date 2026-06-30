# Capacity and saturation

Capacity planning is forecasting; saturation is the present-tense version of the same
question. This page applies Brendan Gregg's **USE method** (Utilisation, Saturation,
Errors) in PromQL, uses `predict_linear` to forecast exhaustion, and computes the
overcommit and headroom ratios that tell you when to add nodes — including OpenStack
nova hypervisor overcommit.

## 1. USE — Utilisation of CPU

```promql
1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))
```

**Purpose:** The **U** in USE for CPU — what fraction of the resource is busy.

**How it works:** Idle fraction averaged across cores, subtracted from 1. Utilisation
answers "how much of the resource is in use"; on its own it doesn't tell you whether work
is *queuing* — that's saturation, query 2. A box can be 70% utilised and badly saturated,
or 95% utilised and fine, depending on the queue.

**Expected output:** Instant vector, 0–1, per host.

**Common modifications:**

- `* 100` for percent.
- `by (cluster)` after a join to roll utilisation up to a cluster.

**Performance:** Cheap. Build a USE dashboard by placing utilisation, saturation, and
errors side by side for each resource.

## 2. USE — Saturation of CPU (run-queue)

```promql
node_load1 / count by (instance) (node_cpu_seconds_total{mode="idle"}) > 1
```

**Purpose:** The **S** in USE for CPU — is work waiting for the resource?

**How it works:** Load per core above 1 means processes are queued for CPU even if
utilisation hasn't pinned to 100%. The run queue is the saturation metric for CPU; for
memory it's swap activity, for disk it's `%util`/queue depth. Saturation is the leading
indicator — it climbs before utilisation maxes out.

**Expected output:** Instant vector, ratio, only for saturated hosts.

**Common modifications:**

- `node_load5` for a steadier signal.
- For memory saturation use `rate(node_vmstat_pswpin[5m]) > 0`.

**Performance:** Cheap. Saturation thresholds should use `for:` to avoid alerting on brief
bursts.

## 3. Predict disk exhaustion (hours to full)

```promql
node_filesystem_avail_bytes{mountpoint="/"}
  /
deriv(node_filesystem_avail_bytes{mountpoint="/"}[6h]) * -1 / 3600
```

**Purpose:** Estimated **hours until full** per filesystem, expressed as a single number
for a panel.

**How it works:** `deriv(...[6h])` is the least-squares slope of available bytes in
bytes/second (negative when filling). Dividing current free bytes by the negative slope
gives seconds-to-empty; `× -1 / 3600` converts to positive hours. Unlike a fixed
threshold, this scales with the actual fill rate.

**Expected output:** Instant vector, hours, per filesystem. Large or negative (draining
hosts) values mean "not soon".

**Common modifications:**

- Clamp with `> 0` to hide filesystems that are emptying.
- Use `predict_linear(...[6h], 24*3600) < 0` to instead get a boolean "full within a day".

**Performance:** `deriv` over `[6h]` is modest; cache via a recording rule if it drives many
panels. Use a fit window several times longer than the noise period.

## 4. Predict memory exhaustion

```promql
predict_linear(node_memory_MemAvailable_bytes[1h], 4 * 3600) < 0
```

**Purpose:** Hosts whose available memory trends to zero within 4 hours — catches slow
leaks.

**How it works:** A linear fit of the last hour of `MemAvailable`, extrapolated 4 hours
forward; `< 0` flags hosts on track to exhaust memory. Because it's trend-based it warns
long before a static "memory < 5%" rule and survives normal sawtooth GC patterns better
than an instantaneous threshold.

**Expected output:** Empty when healthy; one series per host heading for exhaustion.

**Common modifications:**

- Gate with `… and node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.3` so you only predict on already-tight hosts.
- Use `[6h]` fit + `24*3600` horizon for slow-leak detection.

**Performance:** Loads the fit window per host. Pair with `for: 30m`; a steep momentary
slope shouldn't page.

## 5. Predict PersistentVolume exhaustion

```promql
predict_linear(kubelet_volume_stats_available_bytes[6h], 24 * 3600) < 0
  and
kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes < 0.25
```

**Purpose:** PVCs forecast to fill within 24 hours **and** already below 25% free — a
precise, low-noise capacity alert.

**How it works:** The `predict_linear` term forecasts exhaustion; the `and` term requires
the volume to already be tight, which suppresses noisy predictions on large, slowly
changing volumes. Combining a trend with a current-state gate is the general recipe for a
quiet capacity alert.

**Expected output:** Empty when healthy; one series per at-risk PVC, carrying
`namespace`/`persistentvolumeclaim`.

**Common modifications:**

- Tighten the horizon to `6*3600` for faster-filling volumes.
- Drop the `and` gate if you prefer earlier, noisier warnings.

**Performance:** Modest per PVC. Record the available/capacity ratio if you reuse it.

## 6. CPU headroom percentage

```promql
100 * (
  1 - sum(kube_pod_container_resource_requests{resource="cpu"})
      / sum(kube_node_status_allocatable{resource="cpu"})
)
```

**Purpose:** Percent of schedulable CPU still uncommitted cluster-wide — your booking
headroom.

**How it works:** Commitment is total requests over total allocatable; `1 -` is the free
fraction, `× 100` percent. This tells you how many more requesting pods will fit before the
scheduler refuses, independent of live utilisation. When headroom approaches zero, add
nodes even if CPUs look idle.

**Expected output:** Instant vector, 0–100. Plan to scale when it drops below ~15–20%.

**Common modifications:**

- `by (node)` on both sums for per-node headroom and to spot bin-packing imbalance.
- `resource="memory"` for memory headroom.

**Performance:** Cheap. The single most useful capacity number for a managed cluster.

## 7. Memory overcommit ratio (limits vs capacity)

```promql
sum(kube_pod_container_resource_limits{resource="memory"})
  /
sum(kube_node_status_capacity{resource="memory"})
```

**Purpose:** How far memory **limits** exceed physical capacity — the cluster's overcommit
factor.

**How it works:** Summed limits over physical capacity. Above 1.0 the cluster is
overcommitted: if every pod used its full limit simultaneously, nodes would OOM. Some
overcommit is normal and efficient; how much you tolerate depends on how bursty and
correlated your workloads are.

**Expected output:** Instant vector, ratio. `> 1` means overcommitted.

**Common modifications:**

- Use `requests` instead of `limits` for the guaranteed-reservation ratio (should stay ≤ 1).
- `by (node)` to find the most overcommitted nodes.

**Performance:** Cheap. Track requests-overcommit (must be ≤ 1) and limits-overcommit (your
risk appetite) as separate panels.

## 8. OpenStack nova vCPU overcommit

```promql
sum(openstack_nova_vcpus_used) / sum(openstack_nova_vcpus)
```

**Purpose:** Hypervisor vCPU allocation ratio across an OpenStack cloud — how many virtual
CPUs are handed out per physical core.

**How it works:** `openstack_nova_vcpus_used` is allocated vCPUs; `openstack_nova_vcpus` is
the count nova advertises (already inflated by the `cpu_allocation_ratio`). Their ratio
shows how saturated scheduling is against the configured overcommit. Approaching 1 means
nova will soon refuse to schedule new instances on these hosts.

**Expected output:** Instant vector, 0–1 against advertised capacity.

**Common modifications:**

- `by (hostname)` to find the most-packed hypervisors.
- Memory equivalent: `sum(openstack_nova_memory_used_bytes) / sum(openstack_nova_memory_bytes)`.

**Performance:** Cheap. Pair vCPU and memory overcommit — instances are usually constrained
by one or the other, rarely both.

## 9. OpenStack hypervisor memory saturation

```promql
1 - (
  sum by (hostname) (openstack_nova_memory_used_bytes)
  / sum by (hostname) (openstack_nova_memory_bytes)
)
```

**Purpose:** Free memory fraction per hypervisor — where the next large flavour can land.

**How it works:** Used over advertised memory per host, subtracted from 1 for free
headroom. Because nova schedules on *allocated* (flavour) memory, not live guest usage,
this reflects placement capacity, not actual RAM pressure inside guests.

**Expected output:** Instant vector, 0–1, one series per hypervisor.

**Common modifications:**

- `bottomk(5, …)` for the most-packed hosts.
- Cross-check against node-exporter `MemAvailable` on the hypervisor for real (not booked) pressure.

**Performance:** Cheap. Booked vs real memory diverging is normal under overcommit.

## 10. Namespace quota saturation

```promql
kube_resourcequota{type="used"}
  /
kube_resourcequota{type="hard"}
  > 0.9
```

**Purpose:** Namespaces about to hit a ResourceQuota — where teams will start seeing
admission denials.

**How it works:** `kube_resourcequota` exposes `used` and `hard` rows per `(namespace,
resource)`. They share those labels, so the division matches one-to-one and yields the
saturation fraction; `> 0.9` flags quotas above 90%. This catches the "deploys suddenly
rejected" failure before it happens.

**Expected output:** Instant vector, 0–1+, only for near-full quotas, labelled by namespace
and resource.

**Common modifications:**

- Drop the `> 0.9` to graph all quota utilisation.
- Filter `{resource="requests.cpu"}` to focus on a specific constrained resource.

**Performance:** Cheap. Alert with `for: 10m` so a transient burst near a count quota
doesn't page.

## 11. Pod IP exhaustion per node

```promql
sum by (node) (kube_pod_info{host_ip!=""})
  /
max by (node) (kube_node_status_capacity{resource="pods"})
```

**Purpose:** How close each node is to its maximum pod count — the limit that silently
blocks scheduling and, on some CNIs, exhausts the node's IP allocation.

**How it works:** `count`/`sum` of running pods per node over the node's `pods` capacity
gives a 0–1 saturation. `max by (node)` on the capacity guards against duplicate capacity
series. Hitting this ceiling produces `Too many pods` scheduling failures even when CPU and
memory look fine — a frequently-missed capacity dimension.

**Expected output:** Instant vector, 0–1, one series per node. `> 0.9` warrants attention.

**Common modifications:**

- `bottomk(5, …)` inverted, or `topk(5, …)`, to find the most-packed nodes.
- Cross-reference your CNI's per-node IP/ENI limit, which may be lower than the pod cap.

**Performance:** Cheap. A useful third axis alongside CPU and memory headroom.
