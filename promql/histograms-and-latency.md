# Histograms and latency

Latency is a distribution, not a number. Prometheus histograms store cumulative bucket
counts so you can estimate any quantile after the fact and aggregate correctly across
instances. The rules here are strict — get the `by (le)` and the `rate()` right or the
numbers are quietly wrong.

## 1. p95 latency from a histogram

```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(apiserver_request_duration_seconds_bucket[5m]))
)
```

**Purpose:** The 95th-percentile Kubernetes API server request latency across the cluster.

**How it works:** Three layers, inside out. `rate(..._bucket[5m])` converts each
cumulative bucket counter into a per-second rate. `sum by (le)` aggregates those rates
across instances **while preserving the `le` bucket-boundary label** — this is mandatory;
`le` is what `histogram_quantile` reads. `histogram_quantile(0.95, …)` then interpolates
within the bucket that contains the 95th percentile.

**Expected output:** Instant vector, seconds, one series (or one per any label you keep
beyond `le`). Typical control-plane reads sit in the tens of milliseconds.

**Common modifications:**

- `0.50` / `0.99` for p50 / p99 on the same expression.
- Add `verb` to `sum by (le, verb)` for per-verb latency (GET vs LIST vs WATCH).
- Filter `{verb=~"GET|LIST"}` to exclude expensive WATCH long-polls.

**Performance:** Histogram queries are bucket-heavy — cost scales with bucket count ×
series. Always `sum by (le)` to collapse instances before `histogram_quantile`. For
dashboards, record `…:le:rate5m` and run `histogram_quantile` over the recorded series.

## 2. The single most common histogram mistake

```promql
# WRONG — do not aggregate without le:
histogram_quantile(0.95, sum(rate(apiserver_request_duration_seconds_bucket[5m])))
# RIGHT:
histogram_quantile(0.95, sum by (le) (rate(apiserver_request_duration_seconds_bucket[5m])))
```

**Purpose:** Show the error that produces plausible-but-wrong latency numbers.

**How it works:** Dropping `le` in the `sum` destroys the bucket structure;
`histogram_quantile` then has nothing to interpolate over and returns garbage (often
`NaN` or a flat line). The fix is always `sum by (le)` (plus any dimension you want to
keep). Equally, never `histogram_quantile` a single instance's raw bucket without
`rate()` first — you'd be quantiling lifetime totals, not recent traffic.

**Expected output:** The RIGHT form yields seconds; the WRONG form yields nonsense.

**Common modifications:** Keep extra labels by listing them: `sum by (le, handler)`.

**Performance:** Same cost either way — correctness, not speed, is the point.

## 3. p50/p90/p99 in one query for a heatmap legend

```promql
histogram_quantile(0.99, sum by (le) (rate(nginx_ingress_controller_request_duration_seconds_bucket{ingress="checkout"}[5m])))
```

**Purpose:** p99 latency for a single ingress object, the SLO-facing number for a service.

**How it works:** Identical structure to query 1, scoped to one `ingress` with a matcher
and reading the ingress-nginx histogram. Run the same expression with `0.5` and `0.9` on
separate graph series to show the spread; if p50 is flat but p99 climbs, you have tail
latency, not a broad slowdown.

**Expected output:** Instant vector, seconds, one series. Web p99s commonly land in the
100ms–1s range.

**Common modifications:**

- `loki_request_duration_seconds_bucket{route="loki_api_v1_query_range"}` for Loki query latency.
- `sum by (le, path)` to find the slowest route.

**Performance:** Ingress histograms can have high path cardinality — scope with a matcher
before aggregating.

## 4. Average latency from `_sum` / `_count`

```promql
sum(rate(apiserver_request_duration_seconds_sum[5m]))
  /
sum(rate(apiserver_request_duration_seconds_count[5m]))
```

**Purpose:** Mean request latency — cheaper than a quantile and correct to aggregate.

**How it works:** Every histogram ships `_sum` (total observed seconds) and `_count`
(number of observations). Rating both and dividing gives the time-weighted mean over the
window. Means are safe to `sum` across instances (unlike summary quantiles), which makes
this the cheapest cross-fleet latency signal — but a mean hides the tail.

**Expected output:** Instant vector, seconds, one series. Usually lower than p95.

**Common modifications:**

- Add `by (verb)` to both halves for per-verb means.
- Guard the denominator with `> 0` to avoid `NaN` during idle windows.

**Performance:** Very cheap — only two series families, no buckets. Good default for
overview panels; pair with p99 for the tail.

## 5. Apdex score

```promql
(
  sum(rate(http_request_duration_seconds_bucket{le="0.3"}[5m]))
  +
  sum(rate(http_request_duration_seconds_bucket{le="1.2"}[5m]))
) / 2
  /
sum(rate(http_request_duration_seconds_count[5m]))
```

**Purpose:** Apdex — a 0–1 satisfaction score with a 300ms target and 1.2s tolerable
threshold (4× the target).

**How it works:** Apdex = (satisfied + tolerating/2) / total. Because buckets are
cumulative, `le="0.3"` already counts all requests ≤ 300ms (satisfied) and `le="1.2"`
counts all ≤ 1.2s (satisfied + tolerating). Their average numerator gives
satisfied + tolerating/2; dividing by `_count` normalises to total requests.

**Expected output:** Instant vector, dimensionless 0–1. 1.0 is perfect; below ~0.85 users
notice.

**Common modifications:**

- Pick `le` values that actually exist in your histogram's bucket boundaries.
- Add `by (service)` to all three sums for per-service apdex.

**Performance:** Reads only two specific buckets plus `_count` — cheap. The buckets must
exist exactly; PromQL won't interpolate `le="0.3"` if your boundaries are `0.25`/`0.5`.

## 6. Fraction of requests under an SLO threshold

```promql
sum(rate(http_request_duration_seconds_bucket{le="0.5"}[30m]))
  /
sum(rate(http_request_duration_seconds_count[30m]))
```

**Purpose:** The proportion of requests served faster than 500ms — a latency SLI.

**How it works:** Cumulative bucket `le="0.5"` over total `_count` is directly the
"good fraction" for a latency SLO. This is the SLI you feed into error-budget and
burn-rate math, and it avoids quantile interpolation entirely.

**Expected output:** Instant vector, 0–1. A 99% latency SLO wants this ≥ 0.99.

**Common modifications:**

- `1 - (… / …)` to express it as the bad fraction instead.
- Use a 30m or longer window to stabilise the SLI for alerting.

**Performance:** One bucket plus `_count` — very cheap and recording-rule friendly.

## 7. Error-budget burn — availability SLI

```promql
1 - (
  sum(rate(http_requests_total{code=~"5.."}[1h]))
  /
  sum(rate(http_requests_total[1h]))
)
```

**Purpose:** Rolling availability (success ratio) for an availability SLO, the
complement of the error ratio.

**How it works:** The error ratio is 5xx rate over total rate; `1 -` makes it the success
ratio (the SLI). With a 99.9% target, your error budget is 0.1% of requests; this SLI
tells you how much of that budget remains as a rate.

**Expected output:** Instant vector, 0–1, typically very close to 1.

**Common modifications:**

- Compute over multiple windows (`5m`, `1h`, `6h`) for burn-rate alerting (next query).
- Replace the error selector with a latency-bad fraction for a latency SLO.

**Performance:** Cheap. Record numerator and denominator separately so every window reuses
them.

## 8. Multi-window multi-burn-rate alert SLI

```promql
(
  sum(rate(http_requests_total{code=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
) > (14.4 * 0.001)
and
(
  sum(rate(http_requests_total{code=~"5.."}[1h])) / sum(rate(http_requests_total[1h]))
) > (14.4 * 0.001)
```

**Purpose:** The fast-burn condition of a Google-SRE-style SLO alert: a 99.9% target being
burned 14.4× too fast, confirmed on both a short and a long window.

**How it works:** `14.4 × 0.001` is the error rate that would exhaust a 30-day budget in
~2 days (the page-worthy "fast burn"). Requiring **both** the 5m and 1h windows to exceed
it (`and`) makes the alert fire fast on a real spike but ignore a single bad minute — the
short window gives speed, the long window gives confidence. A second alert pairs a
6h/1h burn rate of `6` for slow burns.

**Expected output:** Empty when healthy; a single series when both windows breach.

**Common modifications:**

- Add a 6h+30m pair at burn rate `6` for the slow-burn page.
- Swap the error fraction for `1 - latency_good_fraction` for a latency SLO.

**Performance:** Four rates per alert — record the SLI once per window and reference the
recorded series to keep alert evaluation cheap.

## 9. Summaries — read quantiles directly, never re-aggregate

```promql
go_gc_duration_seconds{quantile="0.99", job="prometheus"}
```

**Purpose:** Prometheus's own p99 garbage-collection pause, straight from a summary metric.

**How it works:** A **summary** computes quantiles client-side and exposes them as the
`quantile` label — there are no buckets and no `histogram_quantile`. You read the value
directly. Critically, you **cannot** average or sum a summary's quantile across instances:
`avg(go_gc_duration_seconds{quantile="0.99"})` is mathematically meaningless. If you need
cross-instance quantiles, the metric must be a histogram instead.

**Expected output:** Instant vector, seconds, one series per instance. GC pauses are
usually sub-millisecond to low-millisecond.

**Common modifications:**

- `{quantile="0.5"}` for the median pause.
- For aggregatable latency, switch the exporter to a histogram and use query 1.

**Performance:** Trivial to read. The cost of summaries is on the client (the exporter),
and their inflexibility (fixed quantiles, no aggregation) is why histograms are preferred.

## 10. Native histograms — the new single-series form

```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds[5m])))
```

**Purpose:** p95 latency using a **native (exponential) histogram**, where the whole
distribution lives in one series instead of dozens of `_bucket` series.

**How it works:** With native histograms (Prometheus 2.40+, opt-in), the metric
`http_request_duration_seconds` is itself a histogram sample — no `le` label, no `_bucket`
suffix. You still `rate()` it and `sum()` it, but there is **no `by (le)`** because the
buckets are internal and dynamically resolved. `histogram_quantile` reads the native
buckets directly. Companion functions include `histogram_count`, `histogram_sum`,
`histogram_fraction(0, 0.5, …)`, and `histogram_avg`.

**Expected output:** Instant vector, seconds — same shape as the classic form, far fewer
underlying series.

**Common modifications:**

- `histogram_fraction(0, 0.5, sum(rate(http_request_duration_seconds[5m])))` for the fraction under 500ms.
- `histogram_count(rate(...))` and `histogram_sum(rate(...))` for a native mean.

**Performance:** The headline win is cardinality: one series replaces an entire `_bucket`
ladder, slashing storage and speeding queries. Requires native-histogram scraping enabled
end to end (exporter, Prometheus, and a compatible TSDB).

## 11. Worst latency handler — combining quantile with topk

```promql
topk(5,
  histogram_quantile(0.99,
    sum by (le, handler) (rate(apiserver_request_duration_seconds_bucket{verb!="WATCH"}[5m]))
  )
)
```

**Purpose:** The five API-server handlers with the worst p99 latency right now.

**How it works:** `sum by (le, handler)` keeps both the bucket label and the dimension you
want to rank; `histogram_quantile` produces a p99 per handler; `topk(5, …)` surfaces the
worst five. Excluding `WATCH` removes long-lived streaming calls that aren't really
"slow".

**Expected output:** Instant vector, up to 5 series, seconds, labelled by handler.

**Common modifications:**

- `sum by (le, path)` for ingress, `(le, route)` for Loki.
- `bottomk` if you instead want the fastest paths for a baseline.

**Performance:** Ranking many handlers' quantiles is the cost; scope with `verb!="WATCH"`
or a namespace matcher first. Don't put `topk` in an alert rule.
