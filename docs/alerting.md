# Alerting

Each dashboard ships **recommended alerts** with full operational context. They are
defined once in the dashboard spec and generated into Prometheus rule files under
[`alerts/`](../alerts/), grouped by domain — so the alert you read about in a
dashboard's doc is exactly the rule you deploy.

## Anatomy of an alert here

Every alert carries more than a threshold:

```yaml
alerts:
  - name: HostHighCPUSaturation
    severity: warning            # info | warning | critical
    expr: 100 * (1 - avg by (instance, job) (rate(node_cpu_seconds_total{mode="idle"}[5m]))) > 90
    for: 10m                     # must hold this long → no flapping
    summary: "Host {{ $labels.instance }} CPU busy > 90% for 10m"
    why: Sustained high CPU starves request handling and raises latency.
    investigate: Open Linux / CPU, scope to the instance, compare iowait vs system vs steal.
    runbook: Identify the top process; if steal is high the hypervisor is oversubscribed.
    recovery: Clears when busy drops below 90% for 5m.
    false_positives: Batch/CI hosts that are intentionally CPU-bound.
```

The `why` / `investigate` / `runbook` / `recovery` / `false_positives` fields are
rendered into both the dashboard doc and the rule's annotations, so on-call has
context at 3am without hunting for a wiki page.

## Deploying the rules

```bash
cp alerts/*.rules.yml /etc/prometheus/rules/
promtool check rules alerts/*.rules.yml      # validate before reload
curl -X POST http://localhost:9090/-/reload
```

Route them through Alertmanager (or Grafana-managed alerting) by `severity`.

## Severity guidance

| Severity | Meaning | Routing |
|----------|---------|---------|
| `critical` | User-visible impact now, or imminent (minutes) | Page immediately |
| `warning` | Degraded / approaching a limit; act within hours | Ticket / business-hours page |
| `info` | Notable, no action required | Dashboard annotation / log |

## Good alert hygiene (applied throughout)

- **`for:` on everything** — a spike isn't an incident; require it to persist.
- **Symptom over cause** — alert on saturation/error/latency the user feels, not
  every underlying metric. One paging alert beats ten noisy ones.
- **Guard division** — `clamp_min(denominator, 1)` and `... or vector(0)` to avoid
  `NaN`/empty results flipping state.
- **Multi-window burn rates** for SLOs — see
  [promql/alerting-patterns.md](../promql/alerting-patterns.md).
- **Dead-man's switch** — alert on `absent(up{job="..."})` so you're told when an
  exporter stops reporting (silence ≠ healthy).

## SLO / burn-rate alerts

For request-driven services, prefer error-budget burn-rate alerts over static
thresholds. The pattern (fast-burn + slow-burn) is documented with copy-paste PromQL
in the [alerting patterns cookbook](../promql/alerting-patterns.md).
