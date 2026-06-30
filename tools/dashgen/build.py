"""Compile every spec under ``tools/specs/`` into the repository artdefacts.

For each ``tools/specs/<category>/<slug>.yaml`` it writes:

* ``dashboards/<category>/<slug>.json``                 (Grafana dashboard)
* ``docs/dashboards/<category>/<slug>.md``              (documentation page)
* ``screenshots/<category>/<slug>.svg``                 (annotated schematic)

and accumulates alert rules into ``alerts/<domain>.rules.yml`` plus a catalog at
``docs/catalog.md`` and ``assets/catalog.json``.

Usage::

    python -m dashgen.build            # build everything
    python -m dashgen.build --quiet     # only print the summary line

Run from the repository root (the directory containing ``tools/`` and
``dashboards/``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# Allow ``python tools/dashgen/build.py`` as well as ``python -m dashgen.build``.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashgen.dashboard import build_dashboard, to_json  # noqa: E402
from dashgen.render import collect_alerts, render_doc, render_svg  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPECS = ROOT / "tools" / "specs"


def _categorize(spec_path: Path) -> tuple[str, str]:
    rel = spec_path.relative_to(SPECS)
    category = rel.parent.as_posix()
    slug = rel.stem
    return category, slug


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build(quiet: bool = False) -> int:
    spec_paths = sorted(SPECS.rglob("*.yaml")) + sorted(SPECS.rglob("*.yml"))
    spec_paths = sorted(set(spec_paths))
    if not spec_paths:
        print("no specs found under tools/specs/", file=sys.stderr)
        return 1

    alerts_by_domain: dict[str, list[dict]] = {}
    catalog: list[dict] = []
    seen_uids: dict[str, str] = {}
    count = 0

    for sp in spec_paths:
        category, slug = _categorize(sp)
        spec = yaml.safe_load(sp.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            print(f"SKIP {sp}: not a mapping", file=sys.stderr)
            continue
        spec.setdefault("uid", f"{category.replace('/', '-')}-{slug}")
        spec.setdefault("title", slug.replace("-", " ").title())

        uid = spec["uid"]
        if uid in seen_uids:
            raise SystemExit(f"duplicate uid {uid!r} in {sp} and {seen_uids[uid]}")
        seen_uids[uid] = str(sp)

        dashboard = build_dashboard(spec)
        _write(ROOT / "dashboards" / category / f"{slug}.json", to_json(dashboard))
        _write(ROOT / "docs" / "dashboards" / category / f"{slug}.md", render_doc(spec, category, slug))
        _write(ROOT / "screenshots" / category / f"{slug}.svg", render_svg(spec, category, slug))

        domain = category.split("/")[0]
        alerts_by_domain.setdefault(domain, []).extend(collect_alerts(spec, category, slug))

        panel_count = sum(len(s.get("panels", [])) for s in spec.get("rows", []))
        catalog.append({
            "title": spec["title"],
            "uid": uid,
            "category": category,
            "slug": slug,
            "domain": domain,
            "datasource": spec.get("datasource", "prometheus"),
            "tags": spec.get("tags", []),
            "panels": panel_count,
            "questions": spec.get("questions", []),
            "json": f"dashboards/{category}/{slug}.json",
            "doc": f"docs/dashboards/{category}/{slug}.md",
            "screenshot": f"screenshots/{category}/{slug}.svg",
            "alerts": len(spec.get("alerts", [])),
        })
        count += 1
        if not quiet:
            print(f"  built {category}/{slug}  ({panel_count} panels, {len(spec.get('alerts', []))} alerts)")

    _write_alerts(alerts_by_domain)
    _write_catalog(catalog)

    total_alerts = sum(len(v) for v in alerts_by_domain.values())
    print(f"dashgen: {count} dashboards, {total_alerts} alert rules, "
          f"{len(alerts_by_domain)} alert groups, catalog with {len(catalog)} entries")
    return 0


def _write_alerts(alerts_by_domain: dict[str, list[dict]]) -> None:
    for domain, rules in sorted(alerts_by_domain.items()):
        if not rules:
            continue
        doc = {"groups": [{"name": f"{domain}.rules", "rules": rules}]}
        out = ROOT / "alerts" / f"{domain}.rules.yml"
        header = (f"# Alerting rules for the {domain} dashboards.\n"
                  f"# Generated from tools/specs/{domain}/**. Do not edit by hand — edit the\n"
                  f"# spec `alerts:` block and re-run `make build`.\n"
                  f"# Load via Prometheus rule_files: or as a Grafana-managed ruleset.\n")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(header + yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, width=100, allow_unicode=True), encoding="utf-8")


def _write_catalog(catalog: list[dict]) -> None:
    catalog = sorted(catalog, key=lambda c: (c["category"], c["slug"]))
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "catalog.json").write_text(
        json.dumps({"dashboards": catalog, "count": len(catalog)}, indent=2) + "\n", encoding="utf-8")

    lines = ["# Dashboard catalog", "",
             f"**{len(catalog)} production-ready dashboards.** Generated by `dashgen` — "
             "do not edit by hand.", "",
             "Each row links to the dashboard JSON, its documentation, and an annotated "
             "schematic screenshot. Import any JSON via *Dashboards → Import* and select your "
             "datasource when prompted.", ""]
    by_domain: dict[str, list[dict]] = {}
    for c in catalog:
        by_domain.setdefault(c["domain"], []).append(c)
    lines.append("## Index")
    lines.append("")
    for domain in sorted(by_domain):
        lines.append(f"- [{domain}](#{domain}) — {len(by_domain[domain])} dashboards")
    lines.append("")
    for domain in sorted(by_domain):
        lines.append(f"## {domain}")
        lines.append("")
        lines.append("| Dashboard | Panels | Alerts | Datasource | JSON · Docs · Screenshot |")
        lines.append("|-----------|:------:|:------:|------------|--------------------------|")
        for c in by_domain[domain]:
            links = (f"[JSON](../{c['json']}) · "
                     f"[Docs](dashboards/{c['category']}/{c['slug']}.md) · "
                     f"[SVG](../{c['screenshot']})")
            lines.append(f"| **{c['title']}** | {c['panels']} | {c['alerts']} | "
                         f"{c['datasource']} | {links} |")
        lines.append("")
    (ROOT / "docs" / "catalog.md").write_text("\n".join(lines), encoding="utf-8")
    _write_matrix(catalog, by_domain)


def _write_matrix(catalog: list[dict], by_domain: dict[str, list[dict]]) -> None:
    """Emit a dashboard <-> datasource/exporter compatibility matrix."""
    m = ["# Compatibility matrix", "",
         "Which datasource and exporters each dashboard needs, and how many panels "
         "and alerts it ships. Generated by `dashgen`.", "",
         "All dashboards target **Grafana 11+** (schema v39) and import into Grafana "
         "10.4+ . Metrics backends are interchangeable where marked Prometheus: "
         "**Prometheus**, **VictoriaMetrics** and **Grafana Mimir** all speak the same "
         "PromQL these dashboards use.", "",
         f"**{len(catalog)} dashboards** · "
         f"{sum(c['panels'] for c in catalog)} panels · "
         f"{sum(c['alerts'] for c in catalog)} alert rules", ""]
    for domain in sorted(by_domain):
        m.append(f"## {domain}")
        m.append("")
        m.append("| Dashboard | Datasource | Tags (exporters) | Panels | Alerts |")
        m.append("|-----------|------------|------------------|:------:|:------:|")
        for c in by_domain[domain]:
            tags = ", ".join(f"`{t}`" for t in c["tags"][:4]) or "—"
            m.append(f"| [{c['title']}](dashboards/{c['category']}/{c['slug']}.md) | "
                     f"{c['datasource']} | {tags} | {c['panels']} | {c['alerts']} |")
        m.append("")
    (ROOT / "docs" / "compatibility-matrix.md").write_text("\n".join(m), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(build(quiet="--quiet" in sys.argv))
