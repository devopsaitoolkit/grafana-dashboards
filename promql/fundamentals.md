# Fundamentals

The building blocks: selecting series, turning counters into rates, aggregating across
labels, shifting time, and the small functions that keep queries robust. Master these
and every later page reads as a combination of them.

## 1. Select series with label matchers

```promql
node_filesystem_avail_bytes{fstype!~"tmpfs|overlay", mountpoint="/"}
```

**Purpose:** Return available bytes on the root filesystem of every host, excluding
ephemeral pseudo-filesystems.

**How it works:** The metric name selects all matching series; the braces filter by
label. `=` is exact match, `!=` not-equal, `=~` regex match, `!~` regex not-match.
Regexes are anchored automatically (`tmpfs|overlay` must match the whole value). Here we
drop `tmpfs` and `overlay` mounts and keep only the `/` mountpoint.

**Expected output:** Instant vector, one sample per host, unit bytes (e.g. `4.2e10`).

**Common modifications:**

- `{mountpoint=~"/|/var|/data"}` to watch several real mounts.
- Drop the matcher entirely to see every filesystem and find noisy mounts.
- `{device!~"/dev/loop.*"}` to ignore Snap loopback devices.

**Performance:** Label matchers are the cheapest filter in PromQL — push them as far
left as possible. A `=~".+"` on `__name__` is the expensive exception; see
[troubleshooting-queries.md](./troubleshooting-queries.md).

## 2. Instant vector vs range vector

```promql
node_network_receive_bytes_total{device="eth0"}[2m]
```

**Purpose:** Show the raw samples behind a counter so you can see what `rate()`
consumes — the difference between an instant and a range vector.

**How it works:** Without a `[…]` duration, a selector is an **instant vector**: one
sample per series at the eval time. Adding `[2m]` makes it a **range vector**: every
sample in the trailing 2 minutes for each series. Range vectors are only useful as the
input to a `*_over_time` or rate-family function; you can't graph one directly.

**Expected output:** A range vector — a list of `(value, timestamp)` pairs per series.
Counter values increase monotonically except across restarts.

**Common modifications:**

- `[$__rate_interval]` in Grafana to auto-size the window to the scrape interval.
- `count_over_time(up[5m])` to count how many scrapes landed in the window.

**Performance:** A range vector loads every sample in the window into memory. Wide
windows over many series (`[1h]` across 100k series) are the classic slow query.

## 3. rate() — the per-second average of a counter

```promql
rate(http_requests_total{job="api"}[5m])
```

**Purpose:** Requests per second for the API service, averaged over 5 minutes.

**How it works:** `rate()` takes the first and last samples in the window, divides the
increase by the time span, and **extrapolates** slightly to the window edges. It
automatically detects counter resets (a drop to a lower value) and treats them as a
restart rather than a negative rate. The result is a smooth per-second figure.

**Expected output:** Instant vector, one series per `(method, code, instance)`
combination still present, unit "per second".

**Common modifications:**

- `sum(rate(http_requests_total{job="api"}[5m]))` for total service throughput.
- `[1m]` for faster reaction in alerts (still ≥ 4 scrapes at 15s).

**Performance:** `rate()` window must be **≥ 4× the scrape interval** or a single
missed scrape zeroes it. `[5m]` is the safe dashboard default; never go below `[1m]`.

## 4. irate() vs rate() — high-resolution spikes

```promql
irate(node_network_transmit_bytes_total{device="eth0"}[5m])
```

**Purpose:** Capture short transmit spikes that `rate()`'s averaging would smooth away.

**How it works:** `irate()` uses only the **last two** samples in the window, so the
`[5m]` here just bounds how far back it will look for that second sample. It reacts
instantly to change but is jagged and can alias on sparse data.

**Expected output:** Instant vector, bytes per second, visibly spikier than `rate()`.

**Common modifications:**

- Use `rate()` for alerts and SLOs; reserve `irate()` for zoomed-in debugging.
- Pair both on one graph to show the smoothing difference.

**Performance:** Same cost as `rate()`. Do **not** use `irate()` in recording rules or
alerts — its volatility causes flapping.

## 5. increase() — how many events in a period

```promql
increase(node_vmstat_pgmajfault[1h])
```

**Purpose:** Total major page faults per host over the last hour.

**How it works:** `increase()` is `rate()` multiplied by the window length, with the
same reset handling and edge extrapolation. It answers "how many" rather than "how
fast". Because of extrapolation the result is a floating-point estimate, not an exact
integer count.

**Expected output:** Instant vector, dimensionless count, one series per host.

**Common modifications:**

- `increase(kube_pod_container_status_restarts_total[1h])` for restarts in the last hour.
- `sum(increase(http_requests_total{code=~"5.."}[1d]))` for daily error volume.

**Performance:** Window must be ≥ 4 scrapes. For exact restart counts over long ranges,
prefer `… - … offset 1h` (see troubleshooting) which avoids extrapolation rounding.

## 6. Aggregate with sum by / sum without

```promql
sum by (job) (rate(http_requests_total[5m]))
```

**Purpose:** Total request rate per job, collapsing all per-instance and per-code series.

**How it works:** `sum by (job)` keeps **only** the `job` label and adds every series
that shares it. The equivalent `sum without (instance, code, method, …)` keeps every
label except the listed ones. Use `by` when you know the few labels you want to keep;
use `without` when you only want to drop one or two noisy labels.

**Expected output:** Instant vector, one series per job, unit per second.

**Common modifications:**

- `avg by (instance)` for a per-host average instead of a sum.
- `max by (cluster)` to find the worst member of a fleet.
- `sum without (cpu) (rate(node_cpu_seconds_total[5m]))` to collapse per-core series.

**Performance:** Aggregation reduces cardinality and speeds up downstream panels. Always
aggregate away `instance`/`pod` before joining or graphing service-level numbers.

## 7. count and count by — how many series

```promql
count by (namespace) (kube_pod_info)
```

**Purpose:** Number of pods per namespace right now.

**How it works:** `count` aggregates by counting series rather than summing values, so
it works on any metric including a constant-`1` info metric like `kube_pod_info`.
`by (namespace)` groups the count per namespace.

**Expected output:** Instant vector, integer count, one series per namespace.

**Common modifications:**

- `count(up == 1)` for the number of healthy targets.
- `count(count by (instance) (node_uname_info))` for the total host count.

**Performance:** Cheap. `count by (__name__)({__name__=~".+"})` is the exception and is a
deliberate cardinality probe — see troubleshooting.

## 8. offset and @ — compare against the past

```promql
sum(rate(http_requests_total[5m]))
  /
sum(rate(http_requests_total[5m] offset 1w)) - 1
```

**Purpose:** This week's traffic versus the same moment last week, as a fractional change.

**How it works:** `offset 1w` shifts the evaluation of that sub-expression one week into
the past while the rest of the query stays at "now". Dividing and subtracting 1 yields a
relative delta (`+0.2` = 20% higher than last week). The `@` modifier instead pins an
expression to an **absolute** timestamp (`… @ 1609459200` or `… @ end()`), useful for
anchoring to a deploy time.

**Expected output:** Scalar-shaped instant vector, dimensionless ratio centered on 0.

**Common modifications:**

- `offset 1d` for day-over-day.
- `<expr> - <expr> offset 5m` to measure short-term change (see troubleshooting).

**Performance:** `offset` doubles the data loaded for that sub-expression. Keep windows
modest when offsetting by long durations.

## 9. avg_over_time and friends — smooth a gauge

```promql
avg_over_time(node_load1[10m])
```

**Purpose:** Ten-minute average of the 1-minute load average, smoothing out spikes.

**How it works:** The `*_over_time` family operates on a **range vector** of a gauge:
`avg_`, `max_`, `min_`, `sum_`, `stddev_`, `quantile_`, `last_`, and `present_over_time`.
Unlike `rate()`, they don't assume the metric is a counter — they aggregate the raw
samples in the window along the time axis, per series.

**Expected output:** Instant vector, same unit as the gauge (load), one series per host.

**Common modifications:**

- `max_over_time(node_memory_MemAvailable_bytes[1h])` for the best-case memory in an hour.
- `quantile_over_time(0.95, node_load1[1h])` for the p95 of load over time.

**Performance:** Cost scales with samples in the window. `[1d]` over thousands of series
is heavy — prefer a recording rule.

## 10. Subqueries — a rate of a rate, or max of a rate

```promql
max_over_time( rate(http_requests_total{job="api"}[5m])[1h:1m] )
```

**Purpose:** The peak per-second request rate seen over the last hour.

**How it works:** The `[1h:1m]` subquery evaluates the inner `rate(...)` every 1 minute
across a 1-hour range, producing a synthetic range vector; `max_over_time` then takes the
highest value. The first duration is the range, the second (after `:`) is the resolution
step. Subqueries let you apply a range function to something that is itself a function.

**Expected output:** Instant vector, per second, one series per surviving label set.

**Common modifications:**

- `deriv( node_filesystem_avail_bytes[1h:5m] )` for the trend of free space.
- `quantile_over_time(0.99, rate(...)[6h:1m])` for the p99 of a rate over time.

**Performance:** Subqueries are expensive — they evaluate the inner expression at every
step. Keep the resolution coarse (`:1m`, not `:15s`) and prefer a recording rule for the
inner rate if you use it often.

## 11. absent and absent_over_time — detect missing data

```promql
absent(up{job="node-exporter", instance="10.0.0.5:9100"})
```

**Purpose:** Fire when a specific target stops reporting entirely — a case `up == 0`
can't catch, because a vanished series produces no `up` sample at all.

**How it works:** `absent()` returns `1` (with the labels you specified) **only when its
argument matches no series**, and returns nothing when the series exists.
`absent_over_time(metric[5m])` is the range version: it's `1` only if the metric had no
samples anywhere in the window, which avoids false positives from a single missed scrape.

**Expected output:** Empty most of the time; a single `1`-valued series with the
specified labels when the target is gone.

**Common modifications:**

- `absent_over_time(up{job="critical"}[10m])` for a debounced dead-target alert.
- Combine with `for: 5m` in an alert rule for extra safety.

**Performance:** Negligible. `absent()` only works when you pin enough labels to name the
expected series — `absent(up)` is useless because some `up` always exists.

## 12. vector(0) fallback and recording-rule basics

```promql
sum(rate(http_requests_total{code=~"5.."}[5m])) or vector(0)
```

**Purpose:** Always return a number for the 5xx rate, even when there are currently zero
errors and the inner expression would otherwise be empty.

**How it works:** When no 5xx series exist, `sum(rate(...))` yields an empty result, which
breaks panels and ratio math. `or vector(0)` supplies a constant `0`-valued series only
when the left side is empty (the `or` operator is a set union that fills gaps). This is the
canonical "no data means zero" guard. A **recording rule** pre-computes such an expression
on a schedule and stores it as a new series:

```yaml
groups:
  - name: api.rules
    interval: 30s
    rules:
      - record: job:http_requests:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))
```

**Expected output:** Instant vector that is never empty; `0` during quiet periods.

**Common modifications:**

- `… or on() vector(0)` when label sets differ and you need an unconditional zero.
- Record both numerator and denominator of an SLO separately, then divide the
  recorded series in the alert for cheap, consistent evaluation.

**Performance:** `vector(0)` is free. Recording rules trade a little storage for big query
speedups — name them `level:metric:operation` (e.g. `job:http_requests:rate5m`) so the
aggregation level is obvious.
