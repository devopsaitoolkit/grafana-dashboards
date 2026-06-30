# Performance & efficient PromQL

Slow dashboards are usually slow PromQL, not slow Grafana. These guidelines (applied
across the library) keep panels snappy even on large fleets.

## Rate windows

Use a range at least **4× the scrape interval** so a counter reset is always covered.
For a 15s scrape that's `[1m]` minimum; the dashboards default to `[5m]` for smooth,
predictable graphs. Too short → spiky/empty; too long → over-smoothed and laggy.

```promql
rate(node_network_receive_bytes_total{instance=~"$instance"}[5m])
```

Prefer `rate()` (per-second average) for graphs. Use `increase()` for "how many in
the window" and `irate()` only for fast-moving, high-resolution debugging.

## Bound cardinality with aggregation

Always reduce to the series you'll actually show. `sum/avg by (instance)` collapses
per-CPU/per-core series into one line per host:

```promql
# good — one series per host
avg by (instance) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))
# bad — one series per host *per cpu* *per mode*
rate(node_cpu_seconds_total[5m])
```

Use `topk(10, ...)` on "top consumer" panels so you never render thousands of series.

## Histograms

Compute quantiles from `_bucket` series, aggregating the `le` label:

```promql
histogram_quantile(0.99, sum by (le) (rate(apiserver_request_duration_seconds_bucket[5m])))
```

Aggregate `le` with `sum by (le, ...)` — never average pre-computed quantiles across
instances; that's mathematically wrong.

## Guard against empty/NaN

Instant stats can be empty (no matching series) and ratios can divide by zero. The
dashboards guard with `or vector(0)` and `clamp_min(denominator, 1)`:

```promql
100 * sum(rate(http_requests_total{code=~"5.."}[5m]))
    / clamp_min(sum(rate(http_requests_total[5m])), 1)
```

## Recording rules for the heavy hitters

When a panel aggregates a high-cardinality metric over a wide range, back it with a
[recording rule](../recording-rules/). It's evaluated once per interval for everyone
instead of on every dashboard load. Each dashboard's **Performance** section names
the rule to use, e.g. `instance:node_cpu_utilisation:rate5m`.

## Dashboard-level levers

- **Default time range** is `now-6h` — wide enough to see trend, narrow enough to
  stay fast. Don't default to 30d.
- **Refresh** defaults to `30s`; raise it on big TV/NOC dashboards.
- **`$__rate_interval`** adapts the window to the zoom level when you frequently
  range from hours to weeks.
- **Max data points** — Grafana down-samples to panel width; you rarely need more.
- Keep a dashboard to a few dozen panels. Split sprawling boards by concern (the
  library does this — e.g. Kubernetes is many focused dashboards, not one giant one).

## Measuring

Use the [Prometheus dashboards](./catalog.md) in this repo (`prometheus/overview`,
`prometheus/tsdb`) to watch query duration, rule evaluation time and head series.
If a single dashboard is slow, the **Query inspector** (panel menu → Inspect → Query)
shows per-query timing.
