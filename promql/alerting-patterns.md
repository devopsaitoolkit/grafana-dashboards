# Alerting patterns

A good alert fires once, on a real problem, with enough context to act — and stays quiet
otherwise. These patterns turn the queries from earlier pages into rules that survive
contact with production: `for:` debouncing, multi-window burn-rate SLOs, dead-target
detection, flap and maintenance suppression, and arithmetic that never divides by zero.
Each query is the **expr** of an alerting rule.

## 1. Threshold with for: debouncing

```promql
node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} < 0.10
```

**Purpose:** Root filesystem below 10% free — paired with `for: 15m` in the rule so a brief
dip doesn't page.

**How it works:** The expression returns a series only while the condition holds. The
rule's `for: 15m` requires it to stay true continuously for 15 minutes before firing,
which absorbs transient blips (a log rotation, a temp file). The expression itself carries
no time logic — `for:` lives in the rule, not the query.

**Expected output:** Empty when healthy; one series per breaching filesystem.

**Common modifications:**

- Tighten to `< 0.05` with a shorter `for: 5m` for a critical tier.
- Pair with a `predict_linear` rule for early warning (see capacity page).

**Performance:** Trivial. Always set `for:` on threshold alerts; instantaneous thresholds
are the top cause of alert fatigue.

## 2. Fast-burn SLO alert (multi-window)

```promql
(
  sum(rate(http_requests_total{code=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
) > (14.4 * 0.001)
and
(
  sum(rate(http_requests_total{code=~"5.."}[1h])) / sum(rate(http_requests_total[1h]))
) > (14.4 * 0.001)
```

**Purpose:** Page when a 99.9% SLO is being burned 14.4× too fast, confirmed on a short and
a long window so it's both quick and trustworthy.

**How it works:** `14.4 × 0.001` is the error rate that exhausts a 30-day budget in ~2
days. The 5m window makes the alert react within minutes; the 1h window prevents a single
bad minute from paging. Requiring `and` between them gives speed without false positives.

**Expected output:** Empty when healthy; one series during a genuine fast burn.

**Common modifications:**

- Add a companion slow-burn rule: burn rate `6` over `6h` and `1h` windows.
- Reference recorded SLI series instead of inlining the four rates.

**Performance:** Four rates per evaluation — record the per-window error ratios once and
divide the recordings. See [histograms-and-latency.md](./histograms-and-latency.md).

## 3. Slow-burn SLO alert (the companion)

```promql
(
  sum(rate(http_requests_total{code=~"5.."}[6h])) / sum(rate(http_requests_total[6h]))
) > (6 * 0.001)
and
(
  sum(rate(http_requests_total{code=~"5.."}[1h])) / sum(rate(http_requests_total[1h]))
) > (6 * 0.001)
```

**Purpose:** Catch a slow, steady error rate that the fast-burn rule ignores but which
would still blow the monthly budget.

**How it works:** Burn rate `6` over a 6h window (confirmed by 1h) flags a smaller error
ratio sustained over hours. Together the fast (14.4) and slow (6) rules give two-speed
coverage: pages for sudden breakage, tickets for slow erosion. This is the standard
Google-SRE multi-burn-rate pair.

**Expected output:** Empty when healthy; one series during a sustained slow burn. Usually
routed as a ticket, not a page.

**Common modifications:**

- Add a 3-day/6h pair at burn rate `1` for the lowest-urgency tier.
- Use a 30m short window on the fast rule for noisier services.

**Performance:** The 6h rate is the heavy term — record it.

## 4. Dead target detection with absent()

```promql
absent(up{job="node-exporter", instance="10.0.0.5:9100"}) == 1
```

**Purpose:** Alert when a specific critical target disappears entirely — which `up == 0`
can't catch, because a vanished target produces no `up` sample at all.

**How it works:** `absent()` returns `1` (with the labels you pinned) only when its
argument matches nothing. You must specify enough labels to identify the expected series;
`absent(up)` is useless because some `up` always exists. Use `absent_over_time(up{...}[10m])`
to debounce a single missed scrape.

**Expected output:** Empty while the target reports; a single `1` series when it's gone.

**Common modifications:**

- `absent_over_time(up{job="critical"}[10m])` for a debounced version.
- Generate per-instance dead-man alerts from a recording rule listing expected instances.

**Performance:** Negligible. Pair with `for: 5m` for extra safety against scrape gaps.

## 5. Dead man's switch (alerting pipeline heartbeat)

```promql
vector(1)
```

**Purpose:** An always-firing alert that proves the entire pipeline — Prometheus,
Alertmanager, and the notification path — is alive. Its **absence** is the signal.

**How it works:** `vector(1)` returns a constant `1`, so the rule always fires. You route
it to a watchdog receiver that expects a steady stream; if notifications stop arriving,
your monitoring itself is down. This is the `Watchdog` alert shipped by kube-prometheus.

**Expected output:** A constant `1` series, always present.

**Common modifications:**

- Route to a heartbeat service (Dead Man's Snitch, healthchecks.io) that pages on silence.
- Add a `severity="none"` label so humans never see it directly.

**Performance:** Free. Every monitoring stack needs exactly one of these.

## 6. Safe division — guard against divide-by-zero

```promql
sum(rate(http_requests_total{code=~"5.."}[5m]))
  /
clamp_min(sum(rate(http_requests_total[5m])), 1)
  > 0.05
```

**Purpose:** A 5xx error-ratio alert that doesn't produce `NaN` (and false-fire) when total
traffic drops to zero.

**How it works:** When the denominator is 0, normal division yields `NaN`, which compares
unpredictably and can fire or mask alerts. `clamp_min(denominator, 1)` forces the
denominator to at least 1, so a quiet period yields a tiny, harmless ratio instead of
`NaN`. The `> 0.05` then only fires on a real 5% error ratio.

**Expected output:** Empty when healthy or idle; a series when the error ratio truly exceeds
5%.

**Common modifications:**

- Add `and sum(rate(http_requests_total[5m])) > 1` to require a minimum traffic floor so you don't alert on 1-in-2 errors during near-idle.
- Use `> 0` filters on the denominator instead of `clamp_min` when you'd rather drop idle series entirely.

**Performance:** Trivial. The traffic-floor `and` is often the better guard — alerting on
error *ratio* at near-zero volume is rarely meaningful.

## 7. Suppress alerts during maintenance with unless

```promql
(
  node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} < 0.10
)
unless on(instance)
(
  node_systemd_unit_state{name="maintenance.target", state="active"} == 1
)
```

**Purpose:** Fire the low-disk alert for every host **except** those currently in a
maintenance window.

**How it works:** `unless` is set subtraction: it returns left-hand series that have **no**
match on the right. `on(instance)` scopes the match to the host. Any host advertising an
active `maintenance.target` is removed from the alert set. This keeps suppression logic in
the query instead of relying solely on Alertmanager silences.

**Expected output:** Breaching hosts, minus those in maintenance.

**Common modifications:**

- Use a synthetic `maintenance_mode{instance=...} == 1` metric pushed via Pushgateway.
- `and on(...)` to require a co-condition instead of suppressing one.

**Performance:** Cheap. For ad-hoc, time-boxed suppression prefer Alertmanager silences;
use `unless` for stable, programmatic conditions.

## 8. Require a correlated condition with and

```promql
(rate(node_disk_io_time_seconds_total[5m]) > 0.95)
  and on(instance, device)
(rate(node_disk_reads_completed_total[5m]) + rate(node_disk_writes_completed_total[5m]) > 50)
```

**Purpose:** Alert on disk saturation **only** when there's real I/O behind it — avoids
paging on a device that reports 95% util while doing a trickle of operations.

**How it works:** The left term is high `%util`; the right requires a meaningful IOPS rate.
`and on(instance, device)` keeps only the `(instance, device)` pairs satisfying both, so a
near-idle disk with a misleading util reading is filtered out. Combining a saturation
signal with a throughput floor is a classic false-positive killer.

**Expected output:** Empty when healthy; a series only for genuinely saturated, busy disks.

**Common modifications:**

- Swap the IOPS floor for a throughput floor in bytes/sec.
- Add `for: 10m` to require sustained saturation.

**Performance:** Cheap. The `on(...)` label set must match both sides exactly.

## 9. Flap avoidance — alert on a stable average

```promql
avg_over_time(
  (rate(http_requests_total{code=~"5.."}[5m]) / rate(http_requests_total[5m]))[15m:1m]
) > 0.05
```

**Purpose:** Fire on a sustained elevated error ratio while ignoring brief spikes — flap
suppression baked into the query.

**How it works:** The subquery `[15m:1m]` evaluates the inner error ratio every minute over
15 minutes; `avg_over_time` averages those samples. A single bad minute barely moves the
15-minute average, so the alert only fires on a genuinely elevated trend. This complements
`for:` — `for:` requires *continuous* breach, while the average tolerates brief dips.

**Expected output:** Empty when healthy; a series when the smoothed ratio exceeds 5%.

**Common modifications:**

- Pair with a modest `for: 5m` for belt-and-braces stability.
- Use `max_over_time` instead if you must catch any spike, not the trend.

**Performance:** Subqueries are expensive — record the inner error ratio and run
`avg_over_time` over the recorded series instead.

## 10. Restart storm with a rate floor

```promql
sum by (namespace, pod) (rate(kube_pod_container_status_restarts_total[15m])) * 900 > 5
  and
sum by (namespace, pod) (kube_pod_status_phase{phase="Running"}) > 0
```

**Purpose:** Alert on pods restarting more than five times in 15 minutes that are still
supposed to be running — a crash loop, not a deleted pod's residue.

**How it works:** `rate(...[15m]) × 900` reconstructs the restart count over the window;
`> 5` is the storm threshold. The `and` against `kube_pod_status_phase{phase="Running"}`
drops pods that are no longer Running, so you don't alert on the dying breath of something
you already deleted. Smoothing via `rate` (vs raw `increase`) keeps the alert from
toggling.

**Expected output:** Empty when healthy; one series per genuinely crash-looping, running
pod.

**Common modifications:**

- Join `kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}` to split OOM loops into their own alert.
- Lower the threshold for production namespaces via a `namespace=~"prod-.*"` matcher.

**Performance:** Cheap. The phase `and` is what makes this alert trustworthy during
deploys and scale-downs.
