# Troubleshooting queries

The ad-hoc queries you paste into Grafana Explore at 3am: what just changed, who's
restarting, who's the top talker, what's blowing up cardinality, and whether Prometheus
itself is healthy. These are exploratory — run them, read them, move on; most aren't
meant to become alerts.

## 1. What changed in the last hour

```promql
topk(20,
  (sum by (__name__, job) (rate({__name__=~"node_.*_total"}[5m])))
  -
  (sum by (__name__, job) (rate({__name__=~"node_.*_total"}[5m] offset 1h)))
)
```

**Purpose:** Which counters are flowing faster now than an hour ago — surface the metrics
that moved when an incident began.

**How it works:** The same rate is evaluated now and `offset 1h`; subtracting gives the
change in per-second rate per metric, and `topk(20, …)` surfaces the biggest movers. A
sudden jump in `node_network_*` or `node_disk_*` totals often pinpoints the subsystem that
broke.

**Expected output:** Instant vector, up to 20 series, delta in per-second units.

**Common modifications:**

- Narrow the `__name__` regex to a subsystem (`node_disk_.*`) to reduce noise.
- Use `bottomk` to find counters that *stopped*.

**Performance:** The `{__name__=~"node_.*_total"}` selector is broad and the `offset`
doubles the load — scope the regex and keep the window at `[5m]`. Don't leave this running
on a dashboard.

## 2. Exact restart count since an hour ago

```promql
(kube_pod_container_status_restarts_total - kube_pod_container_status_restarts_total offset 1h) > 0
```

**Purpose:** Exactly how many times each container restarted in the last hour — no
extrapolation, unlike `increase()`.

**How it works:** Subtracting the counter's value an hour ago from its value now gives the
precise integer increase (assuming no restart of the *process exporting it* in between).
This is the honest counterpart to `increase(...[1h])`, which extrapolates to window edges
and returns fractional counts.

**Expected output:** Instant vector, integer restart delta, only for containers that
restarted.

**Common modifications:**

- `offset 1d` for a daily restart tally.
- Apply the same `now − offset` pattern to `http_requests_total` for exact request counts in a window.

**Performance:** Cheap — two instant reads, no range vector. The `offset` doubles series
loaded but each is a single sample.

## 3. Who restarted (process uptime)

```promql
time() - process_start_time_seconds < 3600
```

**Purpose:** Which exporters/processes started within the last hour — find the thing that
just restarted.

**How it works:** `process_start_time_seconds` is the Unix start time of the process;
`time()` is the evaluation timestamp. Their difference is uptime in seconds; `< 3600` keeps
processes younger than an hour. Most client libraries (Go, Python, Java) export
`process_start_time_seconds`, so this works across many exporters at once.

**Expected output:** Instant vector, uptime in seconds, one series per recently started
process.

**Common modifications:**

- Sort with `bottomk(10, time() - process_start_time_seconds)` for the very newest.
- `node_boot_time_seconds` instead for host (not process) reboots.

**Performance:** Trivial. A fast first move during any "did something restart?" investigation.

## 4. Top talkers — busiest series right now

```promql
topk(10, sum by (instance) (rate(node_network_transmit_bytes_total{device!~"lo|veth.*"}[5m]) * 8))
```

**Purpose:** The ten hosts pushing the most egress bandwidth — find the source of a traffic
surge.

**How it works:** Per-host transmit rate in bits/sec (`× 8`), ranked by `topk(10, …)`.
Swapping the metric makes this a generic "top talkers" tool — point it at request rate, CPU,
disk writes, or error counts to find whoever is dominating that resource.

**Expected output:** Instant vector, up to 10 series, bits/sec.

**Common modifications:**

- `topk(10, sum by (pod) (rate(container_network_transmit_bytes_total[5m])))` for chatty pods.
- `topk(10, sum by (job) (rate(http_requests_total[5m])))` for the busiest service.

**Performance:** The inner aggregation dominates cost. Filter `veth`/`lo` to avoid container
cardinality. Exploratory only — never `topk` in an alert.

## 5. Find a cardinality explosion (by metric name)

```promql
topk(20, count by (__name__) ({__name__=~".+"}))
```

**Purpose:** Which metric names have the most series — the first stop when Prometheus memory
or query latency blows up.

**How it works:** `{__name__=~".+"}` matches every series; `count by (__name__)` counts series
per metric name; `topk(20, …)` surfaces the worst offenders. A single metric with millions
of series (usually from an unbounded label like a user ID, request path, or UUID) is the
classic cause of OOM.

**Expected output:** Instant vector, up to 20 series, integer series-count per metric name.

**Common modifications:**

- `count by (job) ({__name__=~".+"})` to attribute cardinality to a scrape job.
- Use the TSDB status page (`/tsdb-status`) for the same data without query cost.

**Performance:** **Expensive — this touches every series.** Run it sparingly, off your main
Prometheus if possible, and never put it on a refreshing dashboard. The matcher
`{__name__=~".+"}` is the one selector you should normally avoid.

## 6. Find the high-cardinality label on a metric

```promql
count(count by (path) (nginx_ingress_controller_requests))
```

**Purpose:** How many distinct values a suspected label (here `path`) has — confirm which
label is exploding a metric's series count.

**How it works:** The inner `count by (path)` produces one series per distinct `path`; the
outer `count(...)` counts those series, giving the label's cardinality. Run it for each
candidate label (`path`, `status`, `pod`, `user`) to find the unbounded one feeding the
explosion from query 5.

**Expected output:** Scalar-shaped instant vector — a single number, the distinct-value
count.

**Common modifications:**

- Swap `path` for any suspect label.
- `count(count by (le) (some_histogram_bucket))` to sanity-check a histogram's bucket count.

**Performance:** Cost scales with the metric's series count; scope to one metric name (as
here), never to `{__name__=~".+"}`.

## 7. Scrape health overview

```promql
count by (job) (up == 0)
```

**Purpose:** How many targets are down per job — the fastest read on monitoring coverage.

**How it works:** `up` is `1` for a successful scrape and `0` for a failed one. `up == 0`
keeps only failed targets; `count by (job)` totals them per job. A non-zero result means
targets are unreachable or failing to scrape, which means blind spots.

**Expected output:** Instant vector, integer count of down targets per job (ideally empty).

**Common modifications:**

- `up == 0` alone to list the exact down instances.
- `count by (job) (up) - count by (job) (up == 1)` for the same count a different way.

**Performance:** Trivial. `up` is one of the cheapest, most important metrics — alert on it
with `for: 5m`.

## 8. Slow scrape targets

```promql
topk(10, scrape_duration_seconds)
```

**Purpose:** Which targets take longest to scrape — slow targets approach the scrape
timeout and then drop out intermittently.

**How it works:** Prometheus records `scrape_duration_seconds` for every target each scrape.
`topk(10, …)` ranks the slowest. A target nearing your `scrape_timeout` (often 10s) will
flap to `up == 0` under load, creating gappy data; this finds them before they do.

**Expected output:** Instant vector, up to 10 series, seconds. Most targets are well under
1s.

**Common modifications:**

- `scrape_samples_scraped` ranked by `topk` to find targets exposing the most series.
- `scrape_duration_seconds / on(job) group_left() <your scrape_timeout>` for a timeout ratio.

**Performance:** Trivial — these are Prometheus self-metrics, one sample per target.

## 9. Series exposed per target (local cardinality)

```promql
topk(10, scrape_samples_scraped)
```

**Purpose:** Which targets dump the most series per scrape — local cardinality offenders, a
companion to the global view in query 5.

**How it works:** `scrape_samples_scraped` is the number of samples Prometheus ingested from
each target on the last scrape. A single endpoint exposing hundreds of thousands of series
is usually a misbehaving exporter or an app with unbounded labels. `topk(10, …)` surfaces
them by instance.

**Expected output:** Instant vector, up to 10 series, integer sample count per target.

**Common modifications:**

- Compare against `scrape_samples_post_metric_relabel_total` to see how much relabeling drops.
- Sort `bottomk` to find targets that suddenly stopped exposing data.

**Performance:** Trivial. Use this to attribute the global cardinality from query 5 to a
specific exporter.

## 10. Prometheus query and rule-engine health

```promql
rate(prometheus_rule_group_iterations_missed_total[5m]) > 0
```

**Purpose:** Is Prometheus failing to evaluate rule groups on schedule? — a sign the server
is overloaded and your alerts may be late or stale.

**How it works:** `prometheus_rule_group_iterations_missed_total` increments whenever a rule
group's evaluation is skipped because the previous run hadn't finished. A non-zero `rate`
means recording/alerting rules are falling behind — often because an expensive rule (a wide
subquery or `{__name__=~".+"}`) is hogging the evaluation budget.

**Expected output:** Empty when healthy; a series per overloaded rule group.

**Common modifications:**

- `prometheus_rule_evaluation_failures_total` rate for rules that error outright.
- `histogram_quantile(0.99, sum by (le) (rate(prometheus_engine_query_duration_seconds_bucket[5m])))` for p99 query latency on the server itself.

**Performance:** Trivial to read. If this fires, the fix is usually to optimise or record
the heavy rules it points you toward — and to retire any of the broad exploratory queries
above that someone pinned to a dashboard.
