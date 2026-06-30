# PromQL Cookbook

A practical, production-tested reference for **PromQL** — the query language used by
Prometheus, Thanos, Mimir, Cortex and VictoriaMetrics. Every query on these pages
follows the same structure so you can copy, understand, and adapt it:

- a `promql` block with the query
- **Purpose** — the operational question it answers
- **How it works** — the functions and operators, step by step
- **Expected output** — instant vector / range, unit, typical values
- **Common modifications** — realistic variations
- **Performance** — cardinality and rate-window guidance

These queries use real metric names from the standard exporters: `node_exporter`,
`kube-state-metrics`, cAdvisor, the `apiserver`, `mysqld_exporter`,
`postgres_exporter`, `redis_exporter`, `openstack-exporter`, and Prometheus's own
self-metrics.

## What PromQL is

PromQL evaluates expressions over time-series data. A time series is a metric name
plus a set of key/value **labels** (for example
`http_requests_total{method="GET", code="200"}`), and a stream of `(timestamp, value)`
samples. Queries select series with label matchers, transform them with functions,
and aggregate them across labels. Almost everything you graph or alert on is one of
four expression types: **instant vector**, **range vector**, **scalar**, or **string**.

## The data model: four metric types

| Type | What it is | Read it with | Examples |
|------|------------|--------------|----------|
| **Counter** | Monotonically increasing total; resets to 0 on restart | `rate()`, `increase()`, `irate()` — never the raw value | `node_network_receive_bytes_total`, `http_requests_total` |
| **Gauge** | A value that goes up and down | Use directly, or `avg_over_time` / `delta` / `deriv` | `node_memory_MemAvailable_bytes`, `kube_pod_status_phase` |
| **Histogram** | Cumulative `_bucket` series (with `le`), plus `_sum` and `_count` | `histogram_quantile()` over `rate(_bucket[…])` | `apiserver_request_duration_seconds_bucket` |
| **Summary** | Pre-computed `quantile` series, plus `_sum` and `_count` | Read `quantile` directly; you **cannot** re-aggregate across instances | `go_gc_duration_seconds` |

A counter only carries meaning as a **rate of change**. Reading its raw value tells you
how much has accumulated since the last process restart — rarely what you want. Native
histograms (a newer single-series histogram type) are covered in
[histograms-and-latency.md](./histograms-and-latency.md).

## The golden rules

**1. Always `rate()` a counter, and size the window to the scrape interval.**
A `rate`/`increase`/`irate` window must span **at least 4 scrape intervals** so a
single missed scrape can't zero the result. With a 15s scrape, `[1m]` is the floor and
`[5m]` is the safe default for graphing. `rate()` gives a smooth per-second average and
is correct for alerts and dashboards; `irate()` uses only the last two samples and is
for high-resolution zoom-ins; `increase()` is `rate() × window` for "how many in this
period". All three automatically correct for counter resets.

**2. Aggregate with explicit label hygiene.**
`sum without (instance)` keeps every label except the ones you drop; `sum by (job)`
keeps only the ones you name. Aggregating away `instance`/`pod` is how you go from
per-target to per-service numbers. Reserve `by ()` for the final shape you want to graph,
and prefer `without` when you only need to collapse one noisy label.

**3. Quantiles come from buckets, aggregated `by (le)`.**
For a histogram, always compute
`histogram_quantile(0.95, sum(rate(<name>_bucket[5m])) by (le))`. You must `rate()` the
`_bucket` series first, sum **by `le`** (keeping the bucket boundary label), and only
then apply `histogram_quantile`. Averaging the raw quantiles of a summary across
instances is mathematically meaningless — never do it.

**4. Joins need matching labels.** Vector-to-vector math requires identical label sets
unless you scope the match with `on(...)` / `ignoring(...)`, and many-to-one joins
(enriching a metric with `kube_pod_info`, say) need `group_left(...)` /
`group_right(...)`. See [aggregations-and-joins.md](./aggregations-and-joins.md).

**5. Guard against empty results and divide-by-zero.** Use `absent()` to alert on a
metric that has disappeared, `vector(0)` as a fallback, and
`clamp_min(denominator, 1)` or `> 0` filters so a quiet period doesn't produce `NaN`.

## Contents

| File | Covers |
|------|--------|
| [fundamentals.md](./fundamentals.md) | Selectors, instant vs range vectors, rate/irate/increase, aggregation, offset & `@`, subqueries, `absent`, recording rules |
| [aggregations-and-joins.md](./aggregations-and-joins.md) | `by`/`without`, `topk`/`bottomk`, vector matching, `group_left`/`group_right`, `label_replace` |
| [histograms-and-latency.md](./histograms-and-latency.md) | `histogram_quantile`, apdex, error budgets, burn rate, native histograms, summaries vs histograms |
| [node-and-linux.md](./node-and-linux.md) | CPU by mode, memory ratio, disk util & await, fill prediction, network, load, conntrack |
| [kubernetes.md](./kubernetes.md) | Restarts, CPU throttling, requests vs allocatable, memory vs limit, pod phases, PVC fill, apiserver |
| [capacity-and-saturation.md](./capacity-and-saturation.md) | The USE method, `predict_linear`, headroom, overcommit, OpenStack and quota saturation |
| [alerting-patterns.md](./alerting-patterns.md) | `for`, multi-window burn-rate SLOs, `absent()`, flap avoidance, `unless`/`and`, safe division |
| [troubleshooting-queries.md](./troubleshooting-queries.md) | Incident queries: what changed, top talkers, cardinality finders, scrape health |

## How to run these

Paste any query into Grafana's Explore view, the Prometheus expression browser, or
`promtool query instant`. For graphs use a range query; for alert rules use an instant
query that returns a vector only when the condition is true. Adjust label matchers
(`namespace`, `cluster`, `job`, `instance`) to your environment — the metric names are
standard, but the label values are yours.

---

Related: more observability and DevOps guides at <https://devopsaitoolkit.com/guides/>.
