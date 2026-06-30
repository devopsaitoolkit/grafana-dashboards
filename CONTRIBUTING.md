# Contributing

Thanks for helping build the best open collection of production Grafana dashboards.
Operator experience is exactly what makes this library valuable — a dashboard you
actually rely on during incidents is worth more than ten generic ones.

## The one rule: edit specs, not JSON

Every dashboard, its docs page, its screenshot, and its alert rules are **generated**
from a compact YAML spec under [`tools/specs/`](./tools/specs/). You never hand-edit
`dashboards/**.json`. This keeps 100+ dashboards consistent.

```bash
# 1. Scaffold (or copy tools/specs/linux/cpu.yaml, the gold standard)
scripts/new-dashboard.sh kubernetes jobs "Kubernetes / Jobs & CronJobs"

# 2. Edit the spec — see docs/authoring-specs.md for the full format
$EDITOR tools/specs/kubernetes/jobs.yaml

# 3. Build and validate
make build
make validate
```

`make build` regenerates `dashboards/`, `docs/dashboards/`, `screenshots/`, the
`alerts/` rules and the catalog. Commit the spec **and** the generated output.

## What makes a good dashboard here

Read [docs/dashboard-design.md](./docs/dashboard-design.md) and
[docs/authoring-specs.md](./docs/authoring-specs.md). In short:

1. **Answer a question, don't dump metrics.** The first row tells on-call whether
   to dig in within five seconds (saturation, error rate, capacity headroom).
2. **Meaningful units and justified thresholds** on every value panel.
3. **Correct, efficient PromQL** — real metric names, rate windows ≥ 4× scrape,
   aggregations that bound cardinality.
4. **No URLs, datasource UIDs, or credentials** in dashboard JSON. Ever.
5. Include **alerts**, a **troubleshooting** table, and a **Production lessons**
   note explaining why the dashboard exists.

## Local toolchain

```bash
pip install pyyaml jsonschema yamllint
make build && make validate      # dashboards + alerts
python scripts/check-links.py    # internal links
npx markdownlint-cli2 "**/*.md"  # markdown
npx cspell "**/*.md"             # spelling
```

CI runs all of the above. PRs must be green.

## Commit & PR

- One dashboard (or one coherent change) per PR where possible.
- Fill in the PR checklist.
- Be kind and constructive — see the [Code of Conduct](./CODE_OF_CONDUCT.md).

## Licensing

Contributions are accepted under the repository's [Apache-2.0](./LICENSE) license.
