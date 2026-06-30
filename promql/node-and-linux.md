# Node and Linux (node_exporter)

The host-level signals every fleet needs: CPU by mode, real memory pressure, disk
saturation and latency, filesystem-fill prediction, network throughput and errors, load
relative to cores, and conntrack. All queries use `node_exporter` metrics and assume a
`job="node-exporter"` (adjust to your job label).

## 1. CPU utilisation (non-idle) per host

```promql
1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))
```

**Purpose:** Fraction of CPU in use per host, the standard "how busy is this box" signal.

**How it works:** `node_cpu_seconds_total` is a per-core counter of seconds spent in each
mode. `rate(...{mode="idle"}[5m])` gives the fraction of each core spent idle (0–1).
`avg by (instance)` averages across cores to get the host's idle fraction; `1 -` flips it
to busy. Averaging idle (one mode) is cleaner than summing all the busy modes.

**Expected output:** Instant vector, 0–1, one series per host. Multiply by 100 for a
percentage.

**Common modifications:**

- `* 100` for a percentage panel.
- `without (cpu, mode)` style: `sum by (instance) (rate(node_cpu_seconds_total{mode!="idle"}[5m])) / count …` for an explicit busy-sum.
- Add `mode` back (`avg by (instance, mode)`) to break utilisation down by user/system/iowait.

**Performance:** Per-core series can be large on big hosts; aggregating `by (instance)`
early keeps panels fast. `[5m]` is the safe rate window.

## 2. CPU breakdown by mode

```promql
avg by (instance, mode) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))
```

**Purpose:** Where CPU time goes — user, system, iowait, softirq, steal — per host.

**How it works:** Keeping `mode` in the `by()` gives one series per mode. High `iowait`
points at disk; high `steal` points at a noisy hypervisor neighbour; high `softirq` often
means heavy network interrupt load.

**Expected output:** Instant vector, 0–1 per mode, several series per host (good for a
stacked graph).

**Common modifications:**

- Filter `{mode=~"iowait|steal"}` to watch only the pathological modes.
- `topk(5, …{mode="steal"})` to find the worst-stolen VMs.

**Performance:** Same cost as query 1; stacked mode graphs are a classic node dashboard
panel.

## 3. Memory available ratio (the real pressure signal)

```promql
node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes
```

**Purpose:** Fraction of RAM actually available to applications — the correct memory
signal, accounting for reclaimable cache.

**How it works:** `MemAvailable` is the kernel's own estimate of how much memory a new
workload could get without swapping, already excluding unreclaimable slab and counting
reclaimable cache. Dividing by `MemTotal` gives a 0–1 ratio. Do **not** use
`MemFree` — it looks alarmingly low on any healthy box because Linux uses free RAM for
page cache.

**Expected output:** Instant vector, 0–1, one series per host. Below ~0.1 is real pressure.

**Common modifications:**

- `1 - (… / …)` for "used" fraction.
- Fallback for old kernels lacking `MemAvailable`: `(MemFree + Cached + Buffers) / MemTotal`.

**Performance:** Two gauges, no rate — trivial. Labels already match for the division.

## 4. Disk %util — how saturated a device is

```promql
rate(node_disk_io_time_seconds_total[5m])
```

**Purpose:** Fraction of wall-clock time the disk was busy servicing I/O — the saturation
component of the USE method for storage.

**How it works:** `node_disk_io_time_seconds_total` counts seconds the device spent doing
I/O. Its `rate()` is the fraction of each second the disk was busy (0–1), exactly
`iostat`'s `%util`. A value near 1 means the device is the bottleneck regardless of
throughput.

**Expected output:** Instant vector, 0–1, one series per `(instance, device)`.

**Common modifications:**

- `* 100` for percent.
- Filter `{device=~"sd.*|nvme.*"}` to drop loop and dm devices.

**Performance:** Trivial. For SSDs, %util can be misleading (they service I/O in parallel)
— pair with latency below.

## 5. Disk average I/O latency (await)

```promql
rate(node_disk_read_time_seconds_total[5m]) / rate(node_disk_reads_completed_total[5m])
```

**Purpose:** Average read latency per I/O — the `await` column from `iostat`.

**How it works:** `read_time_seconds_total` accumulates time spent on reads;
`reads_completed_total` counts reads. Rating both and dividing gives mean seconds per read.
This is more honest than %util on modern storage because it reflects what callers actually
wait for.

**Expected output:** Instant vector, seconds per I/O, one series per device. Healthy SSDs
are sub-millisecond; spinning disks tens of ms.

**Common modifications:**

- Swap `read` → `write` for write latency.
- Guard with `rate(...reads_completed_total[5m]) > 0` to suppress `NaN` on idle disks.

**Performance:** Cheap. Watch for divide-by-zero on idle devices — add the `> 0` guard in
alerts.

## 6. Predict filesystem exhaustion

```promql
predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h], 4 * 3600) < 0
```

**Purpose:** Will the root filesystem run out of space in the next 4 hours at the current
trend? — a capacity early-warning.

**How it works:** `predict_linear(range, seconds)` fits a least-squares line to the last 6
hours of available bytes and extrapolates `seconds` into the future. Comparing to `< 0`
yields a series only for filesystems projected to hit zero within 4 hours. This catches
steady leaks long before a static threshold would.

**Expected output:** Empty when healthy; one series per filesystem heading for exhaustion.

**Common modifications:**

- `predict_linear(…[1h], 4*3600) < 0` reacts faster but is noisier.
- Combine with `node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.2` so you only predict on already-tight disks.

**Performance:** Loads 6h of samples per filesystem — modest. Use a longer fit window
(`[6h]`) than your prediction horizon for a stable slope; pair with a `for: 15m` to avoid
transient slopes.

## 7. Filesystem fill percentage

```promql
100 * (1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})
```

**Purpose:** Percent full per real filesystem — the everyday disk gauge.

**How it works:** `avail / size` is the free fraction; `1 -` makes it used, `× 100` makes
it percent. Excluding `tmpfs`/`overlay` removes pseudo-filesystems whose "fullness" is
meaningless. Note `avail` reflects the non-root reservation, so this matches what users
actually see from `df`.

**Expected output:** Instant vector, 0–100, one series per filesystem.

**Common modifications:**

- Use `size - avail`/`size` if you want to include the root-reserved blocks.
- `topk(10, …)` for the fullest disks across a fleet.

**Performance:** Trivial. The `fstype` filter both reduces noise and trims cardinality.

## 8. Network throughput in bits per second

```promql
rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*"}[5m]) * 8
```

**Purpose:** Inbound network throughput per interface in bits/sec (to compare against link
speed).

**How it works:** The counter is in **bytes**; `rate()` gives bytes/sec and `× 8` converts
to bits/sec, which is how NICs are rated (a "1 Gbps" link is 125 MB/s). Excluding
loopback, veth, and docker bridges focuses on real uplinks.

**Expected output:** Instant vector, bits/sec, one series per interface.

**Common modifications:**

- Swap `receive` → `transmit` for egress.
- Divide by `node_network_speed_bytes * 8` for link utilisation as a fraction.

**Performance:** Trivial. veth/docker interfaces explode cardinality on container hosts —
always filter them out.

## 9. Network errors and drops

```promql
rate(node_network_receive_errs_total[5m]) + rate(node_network_receive_drop_total[5m])
```

**Purpose:** Receive-side error + drop rate per interface — a NIC/cabling/buffer health
signal.

**How it works:** Two counters summed after rating: `errs` are malformed frames, `drop`
are frames discarded for lack of buffer/queue. Any sustained non-zero value is abnormal on
a healthy wired interface and usually points at hardware, MTU mismatch, or ring-buffer
saturation.

**Expected output:** Instant vector, errors/sec, ideally `0` everywhere.

**Common modifications:**

- Add `transmit_errs_total` + `transmit_drop_total` for egress.
- `> 0` filter to list only interfaces actively erroring.

**Performance:** Trivial. Alert on `> 0` for `for: 10m` rather than instantaneously, since
a single dropped frame is normal during bursts.

## 10. Load average relative to core count

```promql
node_load1 / count by (instance) (node_cpu_seconds_total{mode="idle"})
```

**Purpose:** Run-queue pressure normalised to cores — a load of 8 means nothing until you
know the core count.

**How it works:** `count by (instance) (node_cpu_seconds_total{mode="idle"})` counts one
`idle` series per logical core, i.e. the core count. Dividing `node_load1` by it gives load
per core; `1.0` means fully subscribed, `> 1` means processes are queuing for CPU.

**Expected output:** Instant vector, ratio, one series per host. Sustained `> 1` is
saturation.

**Common modifications:**

- Use `node_load5` or `node_load15` for less twitchy signals.
- Multiply by 100 for a "load %" gauge.

**Performance:** Cheap. The `count` of idle series is a reliable, exporter-agnostic way to
get core count without `machine_cpu_cores`.

## 11. Conntrack table utilisation

```promql
node_nf_conntrack_entries / node_nf_conntrack_entries_limit
```

**Purpose:** How close the kernel connection-tracking table is to full — overflow drops
new connections silently.

**How it works:** `entries` is the current tracked-connection count; `entries_limit` is
`nf_conntrack_max`. The ratio is 0–1; above ~0.8 you risk
`nf_conntrack: table full, dropping packet`, which manifests as mysterious connection
failures on busy gateways, NAT boxes, and ingress nodes.

**Expected output:** Instant vector, 0–1, one series per host (only where conntrack is
loaded).

**Common modifications:**

- `* 100` for percent.
- `topk(5, …)` to find the busiest NAT/ingress nodes.

**Performance:** Two gauges — trivial. Alert at `> 0.8` for `for: 5m`; sustained high
conntrack usually needs a larger `nf_conntrack_max` or connection-reuse fixes.

## 12. Memory + swap pressure with a fallback

```promql
(
  (node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes)
  / clamp_min(node_memory_SwapTotal_bytes, 1)
) and (node_memory_SwapTotal_bytes > 0)
```

**Purpose:** Swap utilisation per host, safely returning nothing for swapless hosts instead
of `NaN`.

**How it works:** `SwapTotal - SwapFree` is swap in use; dividing by `SwapTotal` gives the
fraction. `clamp_min(…, 1)` prevents a divide-by-zero on swapless hosts (where `SwapTotal`
is 0), and `and (SwapTotal > 0)` then drops those hosts from the result entirely so they
don't show a misleading `0`. Active swapping on a server usually signals real memory
pressure.

**Expected output:** Instant vector, 0–1, only for hosts that actually have swap.

**Common modifications:**

- Pair with `rate(node_vmstat_pswpin[5m])` to see swap-in *activity*, which matters more than static usage.
- `* 100` for percent.

**Performance:** Trivial. The `clamp_min` + `and` pattern is the general recipe for safe
ratios — see [alerting-patterns.md](./alerting-patterns.md).

## 13. Clock drift against NTP

```promql
abs(node_timex_offset_seconds) > 0.05
```

**Purpose:** Hosts whose clock has drifted more than 50ms from NTP — clock skew breaks
TLS, distributed locks, log correlation, and certificate validation.

**How it works:** `node_timex_offset_seconds` is the kernel's current estimate of how far
the system clock is from true time (from `adjtimex`). `abs(...)` makes the sign irrelevant
(fast or slow), and `> 0.05` flags meaningful drift. A growing offset usually means the NTP
daemon is dead or unreachable.

**Expected output:** Empty when healthy; one series per drifting host, seconds of offset.

**Common modifications:**

- `node_timex_sync_status == 0` to find hosts whose clock is not synchronised at all.
- Tighten to `> 0.01` for latency-sensitive or consensus workloads.

**Performance:** Trivial. Alert with `for: 10m` since the offset estimate jitters slightly
between scrapes.
