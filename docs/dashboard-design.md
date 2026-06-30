# Dashboard design principles

Every dashboard in this repository follows the same philosophy: **answer the
operational question, don't display the metric.** A dashboard is a decision tool
for someone who is paged at 3am, not a museum of gauges.

## 1. Lead with the headline signal

The first row must let an on-call engineer decide *in five seconds* whether to dig
in. That means **saturation, error rate, or capacity headroom** as `stat`/`gauge`
panels with color thresholds — not a wall of raw counters. Detail comes in later
rows. The reference dashboard (`Linux / CPU`) leads with "hosts saturated", "busiest
host", "fleet mean" and "max steal" before it ever draws a time series.

## 2. The four signals

Structure panels around proven methods rather than whatever the exporter happens to
expose:

- **RED** (request-driven services): Rate, Errors, Duration.
- **USE** (resources): Utilisation, Saturation, Errors.
- **The four golden signals**: latency, traffic, errors, saturation.

API server, ingress and database dashboards use RED. Node, disk, hypervisor and
capacity dashboards use USE.

## 3. Meaningful units, always

Every value panel declares a Grafana unit (`percent`, `bytes`, `Bps`, `s`, `ms`,
`ops`, `reqps`, …). A number without a unit is a bug. Use `percentunit` (0–1) vs
`percent` (0–100) deliberately and keep the PromQL consistent with the unit.

## 4. Thresholds encode meaning

Green = within expectations, yellow = investigate (approaching a limit), red = act
now (breached). Don't add a threshold you can't justify against an SLO or a physical
limit. Thresholds drive both the panel color and the annotated screenshot legend.

## 5. Repeatable variables

Dashboards are templated with variables (`job`, `instance`, `cluster`, `namespace`)
so one dashboard serves the whole fleet. Multi-value variables with `includeAll`
let you go from fleet to a single host without editing anything. See
[variables.md](./variables.md).

## 6. Portable datasources

Panels reference the datasource as an **input** (`${DS_PROMETHEUS}` / `${DS_LOKI}`),
never a hardcoded UID. Importing prompts for the datasource; provisioning binds it
by UID. This is why the same JSON works on anyone's Grafana.

## 7. Efficient PromQL

Rate windows are at least 4× the scrape interval (`[5m]` for a 15s scrape).
Aggregations use `by`/`without` to bound series count. Expensive expressions on
large fleets are backed by [recording rules](../recording-rules/). See
[performance.md](./performance.md).

## 8. Layout & UX

- 24-column grid; headline `stat`s at 6 columns, time series at 12, full-width
  tables at 24.
- Logical rows with descriptive titles ("Saturation — read first").
- Consistent legends: `table` mode with `last/max/mean` calcs for comparison
  panels, `list` for a few series, `hidden` when the value panel speaks for itself.
- Dark-mode native colors; mobile/responsive via the standard grid.

## 9. Every dashboard ships with

- A **Production lessons** note — *why* it exists and how it's been used.
- **Recommended alerts** with runbook context.
- A **troubleshooting** table for the common "no data / wrong data" traps.

These aren't optional extras; they're what turn a picture into a tool.
