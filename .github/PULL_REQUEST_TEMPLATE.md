<!-- Thanks for contributing! Dashboards are generated from specs — edit the spec,
     not the JSON. Run `make build && make validate` before pushing. -->

## What does this PR do?

<!-- New dashboard? Fix to a query? Tooling/docs? One or two sentences. -->

## Checklist

- [ ] I edited the **spec** under `tools/specs/`, not the generated JSON.
- [ ] `make build` regenerates with no other diffs.
- [ ] `make validate` passes (0 errors).
- [ ] New dashboards **answer operational questions** and lead with the headline signal.
- [ ] Every value panel has a **meaningful unit**; thresholds are justified.
- [ ] PromQL uses **real metric names** and bounded rate windows (≥ 4× scrape).
- [ ] No URLs, datasource UIDs, or credentials in any dashboard JSON.
- [ ] Docs/screenshots regenerated (they're produced by `make build`).

## Dashboards added/changed

<!-- e.g. dashboards/kubernetes/jobs.json — Kubernetes / Jobs & CronJobs -->
