# Transformations

Transformations reshape query results *after* PromQL but *before* the panel renders —
ideal for tables and composite stats. Several dashboards use them; this is how and
when.

## When to reach for a transformation

- Turn multiple instant queries into **one table row per object** (Organize +
  Merge / Join by field).
- Compute a **ratio or delta between two queries** without a single hairy PromQL
  expression (Add field from calculation).
- **Rename/hide** noisy label columns for a clean table (Organize fields).
- **Filter** to the rows that matter (Filter data by values).

Prefer doing math in PromQL when it's simple; reach for transformations when joining
*different* queries or building human-readable tables.

## Common recipes

### One row per object (join several metrics)

Query each metric as an **instant** query with `format: table`, then:

1. **Merge** (or **Join by field** on `instance`/`pod`) to put them in one table.
2. **Organize fields** to rename `Value #A` → "CPU", `Value #B` → "Memory", and
   reorder/hide the rest.

```yaml
# spec excerpt — a per-host table
- type: table
  title: Host summary
  transformations:
    - id: merge
    - id: organize
      options:
        renameByName: {"Value #A": "CPU %", "Value #B": "Mem %", instance: "Host"}
        excludeByName: {job: true, __name__: true}
  targets:
    - {expr: "100 * instance:node_cpu_utilisation:rate5m", instant: true, format: table, refId: A}
    - {expr: "100 * instance:node_memory_utilisation:ratio", instant: true, format: table, refId: B}
```

### A ratio between two queries

Use **Add field from calculation → Binary operation** (`A / B`) when expressing the
ratio in PromQL would require an awkward join.

### Top-N table

Query with `topk(10, ...)`, `format: table`, then **Sort by** the value column
descending and **Organize** to tidy columns.

## Gotchas

- Transformations run in order — a Filter before a Merge sees different data than
  after. Drag to reorder.
- For tables, set targets to **`instant: true`** and **`format: table`**; range
  vectors produce a time column you rarely want.
- Heavy transformations move work to the browser. For big result sets, reduce in
  PromQL first (`topk`, `by`).

See [authoring-specs.md](./authoring-specs.md) for the `transformations:` field, and
Grafana's docs for the full transformation list.
