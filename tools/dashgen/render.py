"""Render the human-facing artdefacts from a dashboard spec.

A spec is the single source of truth. From it we generate, deterministically:

* ``render_doc``   -> a complete Markdown documentation page;
* ``render_svg``   -> an annotated schematic "screenshot" (SVG, version-control
  friendly, honest about being a layout schematic rather than a pixel capture);
* ``render_alerts``-> Prometheus alerting rules (the same alert defs that appear
  in the doc), so alerts are defined once and never drift from the docs.
"""

from __future__ import annotations

import html
from typing import Any

PROMO_LINKS = {
    "guides": "https://devopsaitoolkit.com/guides/",
    "incident": "https://devopsaitoolkit.com/dashboard/incident-response",
    "blog": "https://devopsaitoolkit.com/blog/",
    "home": "https://devopsaitoolkit.com",
    "newsletter": "https://devopsaitoolkit.com/newsletter",
}


# --- documentation -------------------------------------------------------------


def _cell(value: Any) -> str:
    """Make a value safe to drop into a Markdown table cell."""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_doc(spec: dict[str, Any], category: str, slug: str) -> str:
    title = spec["title"]
    seo = spec.get("seo_phrase", title)
    # Relative prefixes depend on how deep the category nests (e.g. openstack/nova).
    segs = category.split("/")
    to_docs = "../" * (1 + len(segs))   # doc file dir -> docs/
    to_root = "../" * (2 + len(segs))   # doc file dir -> repo root
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> {spec.get('description', '')}")
    lines.append("")
    lines.append(f"**Primary search phrase:** {seo}  ")
    lines.append(f"**Category:** `{category}` · **UID:** `{spec['uid']}` · "
                 f"**Datasource:** {spec.get('datasource', 'prometheus').title()}")
    lines.append("")
    lines.append(f"![{title} dashboard]({to_root}screenshots/{category}/{slug}.svg)")
    lines.append("")

    # Questions answered.
    if spec.get("questions"):
        lines.append("## Questions this dashboard answers")
        lines.append("")
        for q in spec["questions"]:
            lines.append(f"- {q}")
        lines.append("")

    # Production lessons.
    if spec.get("production_lessons"):
        lines.append("## Production lessons — why this dashboard exists")
        lines.append("")
        lines.append(spec["production_lessons"])
        lines.append("")

    # Data source requirements.
    lines.append("## Data source requirements")
    lines.append("")
    ds = spec.get("datasource", "prometheus").title()
    lines.append(f"- **{ds}** datasource (selected at import time via `${{DS_{spec.get('datasource','prometheus').upper()}}}`).")
    for req in spec.get("data_sources", []):
        lines.append(f"- {req}")
    lines.append("")

    # Variables.
    if spec.get("templating"):
        lines.append("## Template variables")
        lines.append("")
        lines.append("| Variable | Label | Type | Purpose |")
        lines.append("|----------|-------|------|---------|")
        for v in spec["templating"]:
            lines.append(f"| `${{{v['name']}}}` | {_cell(v.get('label', v['name']))} | "
                         f"{v.get('type', 'query')} | {_cell(v.get('description') or '—')} |")
        lines.append("")

    # Panels by row.
    lines.append("## Panels")
    lines.append("")
    for section in spec.get("rows", []):
        lines.append(f"### {section.get('title', 'Panels')}")
        lines.append("")
        for p in section.get("panels", []):
            if p["type"] == "text":
                continue
            lines.append(f"- **{p.get('title', 'Panel')}** ({p['type']}"
                         + (f", `{p['unit']}`" if p.get("unit") else "") + ")"
                         + (f" — {p['description']}" if p.get("description") else ""))
        lines.append("")

    # Import.
    lines.append("## Import")
    lines.append("")
    lines.append("**Grafana UI** — *Dashboards → New → Import*, upload "
                 f"`dashboards/{category}/{slug}.json`, then pick your datasource when prompted.")
    lines.append("")
    lines.append("**API:**")
    lines.append("")
    lines.append("```bash")
    lines.append(f"scripts/import-dashboard.sh dashboards/{category}/{slug}.json")
    lines.append("```")
    lines.append("")
    lines.append("**Provisioning** — drop the JSON into a provisioned folder (see "
                 f"[provisioning guide]({to_docs}provisioning.md)).")
    if spec.get("import_notes"):
        lines.append("")
        lines.append(spec["import_notes"])
    lines.append("")

    # Alerts.
    if spec.get("alerts"):
        lines.append("## Recommended alerts")
        lines.append("")
        lines.append(f"Ready-to-use rules ship in `alerts/{category.split('/')[0]}.rules.yml`.")
        lines.append("")
        for a in spec["alerts"]:
            lines.append(f"### {a['name']} (`{a.get('severity', 'warning')}`)")
            lines.append("")
            lines.append("```promql")
            lines.append(a["expr"])
            lines.append("```")
            lines.append("")
            lines.append(f"- **Fires after:** `{a.get('for', '5m')}`")
            lines.append(f"- **Why it matters:** {a.get('why', '')}")
            lines.append(f"- **Investigate:** {a.get('investigate', '')}")
            lines.append(f"- **Recovery:** {a.get('recovery', '')}")
            lines.append(f"- **False positives:** {a.get('false_positives', '')}")
            lines.append("")

    # Troubleshooting.
    if spec.get("troubleshooting"):
        lines.append("## Troubleshooting")
        lines.append("")
        lines.append("| Symptom | Likely cause | First action |")
        lines.append("|---------|--------------|--------------|")
        for t in spec["troubleshooting"]:
            lines.append(f"| {_cell(t['symptom'])} | {_cell(t['cause'])} | {_cell(t['action'])} |")
        lines.append("")

    # Performance.
    lines.append("## Performance considerations")
    lines.append("")
    lines.append(spec.get("performance",
                 "Queries use rate windows of at least 4× the scrape interval and aggregate "
                 "with `by`/`without` to bound cardinality. Widen the time range gradually on "
                 "high-cardinality fleets; prefer recording rules (see `recording-rules/`) for "
                 "expensive expressions rendered on large dashboards."))
    lines.append("")

    # Customization.
    lines.append("## Customization")
    lines.append("")
    lines.append(spec.get("customization",
                 "Adjust thresholds in the panel field config to match your SLOs. Use the "
                 "template variables to scope to a job, cluster or instance. To extend the "
                 "dashboard, edit the spec in `tools/specs/` and re-run `make build` so the "
                 "JSON, docs and screenshot stay in sync."))
    lines.append("")

    # Further reading (the only place promo links live).
    lines.append("## Related resources")
    lines.append("")
    lines.append(f"- [Advanced observability guides]({PROMO_LINKS['guides']})")
    lines.append(f"- [Grafana & Prometheus tutorials]({PROMO_LINKS['blog']})")
    lines.append(f"- [AI Incident Response Assistant]({PROMO_LINKS['incident']})")
    lines.append(f"- [PromQL cookbook]({to_root}promql/README.md) · "
                 f"[Alerting guide]({to_docs}alerting.md) · "
                 f"[Dashboard catalog]({to_docs}catalog.md)")
    lines.append("")
    return "\n".join(lines)


# --- annotated SVG schematic ---------------------------------------------------

_BG = "#0b0c0e"
_PANEL = "#181b1f"
_BORDER = "#2c3235"
_ROW = "#22252b"
_TEXT = "#d8d9da"
_MUTED = "#8e8e8e"
_ACCENT = "#3274d9"
_GOOD = "#73bf69"
_WARN = "#f2cc0c"
_BAD = "#e02f44"

GRID_W = 24
CELL = 44  # px per grid column
UNIT_H = 30  # px per grid row unit
PAD = 16
ANNO_W = 300


def render_svg(spec: dict[str, Any], category: str, slug: str) -> str:
    from .dashboard import _layout  # local import to avoid cycle

    panels = _layout(spec.get("rows", []), spec.get("datasource", "prometheus"))
    max_y = 0
    for p in panels:
        gp = p["gridPos"]
        max_y = max(max_y, gp["y"] + gp["h"])
    board_w = GRID_W * CELL
    board_h = max_y * UNIT_H
    total_w = PAD * 3 + board_w + ANNO_W
    total_h = PAD * 2 + board_h + 40

    def esc(s: str) -> str:
        return html.escape(str(s), quote=True)

    out: list[str] = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
               f'viewBox="0 0 {total_w} {total_h}" font-family="Inter, Roboto, Arial, sans-serif">')
    out.append(f'<rect width="{total_w}" height="{total_h}" fill="{_BG}"/>')
    # Title bar.
    out.append(f'<text x="{PAD}" y="{PAD+14}" fill="{_TEXT}" font-size="16" font-weight="600">{esc(spec["title"])}</text>')
    out.append(f'<text x="{PAD}" y="{PAD+32}" fill="{_MUTED}" font-size="11">Schematic layout · datasource: '
               f'{esc(spec.get("datasource","prometheus"))} · uid: {esc(spec["uid"])}</text>')

    ox, oy = PAD, PAD + 40
    type_color = {"stat": _ACCENT, "gauge": _GOOD, "timeseries": _ACCENT, "table": _MUTED,
                  "heatmap": _BAD, "bargauge": _WARN, "piechart": _GOOD, "logs": _MUTED,
                  "state-timeline": _WARN}
    for p in panels:
        gp = p["gridPos"]
        x = ox + gp["x"] * CELL
        y = oy + gp["y"] * UNIT_H
        w = gp["w"] * CELL
        h = gp["h"] * UNIT_H
        if p["type"] == "row":
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h-4}" fill="{_ROW}" rx="3"/>')
            out.append(f'<text x="{x+10}" y="{y+19}" fill="{_TEXT}" font-size="12" font-weight="600">▾ {esc(p["title"])}</text>')
            continue
        accent = type_color.get(p["type"], _ACCENT)
        out.append(f'<rect x="{x+2}" y="{y+2}" width="{w-4}" height="{h-6}" fill="{_PANEL}" stroke="{_BORDER}" rx="3"/>')
        out.append(f'<rect x="{x+2}" y="{y+2}" width="{w-4}" height="3" fill="{accent}" rx="2"/>')
        out.append(f'<text x="{x+10}" y="{y+20}" fill="{_TEXT}" font-size="11" font-weight="500">{esc(p["title"][:42])}</text>')
        out.append(f'<text x="{x+10}" y="{y+34}" fill="{_MUTED}" font-size="9">{esc(p["type"])}'
                   + (f' · {esc(p["fieldConfig"]["defaults"].get("unit",""))}' if p.get("fieldConfig", {}).get("defaults", {}).get("unit") else "")
                   + '</text>')
        # mini sparkline / glyph hint
        cy = y + h / 2 + 6
        if p["type"] in ("timeseries", "state-timeline"):
            pts = " ".join(f"{x+12+i*((w-24)/6):.0f},{cy - (8 if i%2 else -6):.0f}" for i in range(7))
            out.append(f'<polyline points="{pts}" fill="none" stroke="{accent}" stroke-width="1.5" opacity="0.8"/>')
        elif p["type"] in ("stat", "gauge"):
            out.append(f'<text x="{x+w/2:.0f}" y="{cy+10:.0f}" fill="{accent}" font-size="20" font-weight="700" text-anchor="middle">●</text>')
        elif p["type"] in ("bargauge", "table", "piechart", "heatmap", "logs"):
            for i in range(3):
                bw = (w - 24) * (0.5 + 0.15 * i)
                out.append(f'<rect x="{x+12}" y="{cy-6+i*9:.0f}" width="{bw:.0f}" height="5" fill="{accent}" opacity="{0.7-0.15*i:.2f}" rx="2"/>')

    # Annotations panel.
    ax = ox + board_w + PAD
    ay = oy
    out.append(f'<rect x="{ax}" y="{ay}" width="{ANNO_W-PAD}" height="{board_h}" fill="{_PANEL}" stroke="{_BORDER}" rx="4"/>')
    ty = ay + 22
    out.append(f'<text x="{ax+12}" y="{ty}" fill="{_TEXT}" font-size="12" font-weight="700">What to look for</text>')
    ty += 20
    notes = spec.get("annotations_help") or _default_help(spec)
    for label, color in notes:
        out.append(f'<circle cx="{ax+18}" cy="{ty-4}" r="4" fill="{color}"/>')
        for j, line in enumerate(_wrap(label, 40)):
            out.append(f'<text x="{ax+30}" y="{ty+j*13}" fill="{_MUTED}" font-size="10">{esc(line)}</text>')
        ty += 13 * len(_wrap(label, 40)) + 8
    out.append('</svg>')
    out.append("")
    return "\n".join(out)


def _default_help(spec: dict[str, Any]) -> list[tuple[str, str]]:
    notes: list[tuple[str, str]] = []
    for q in spec.get("questions", [])[:4]:
        notes.append((q, _ACCENT))
    notes.append(("Green: within expected range", _GOOD))
    notes.append(("Yellow: investigate — approaching a limit", _WARN))
    notes.append(("Red: act now — threshold breached", _BAD))
    return notes


def _wrap(text: str, width: int) -> list[str]:
    words = str(text).split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [""]


# --- Prometheus alert rules ----------------------------------------------------


def collect_alerts(spec: dict[str, Any], category: str, slug: str) -> list[dict[str, Any]]:
    rules = []
    for a in spec.get("alerts", []):
        rule = {
            "alert": a["name"],
            "expr": a["expr"],
            "for": a.get("for", "5m"),
            "labels": {"severity": a.get("severity", "warning")},
            "annotations": {
                "summary": a.get("summary", a["name"]),
                "description": a.get("why", ""),
                "runbook": a.get("runbook", ""),
                "dashboard": f"dashboards/{category}/{slug}.json",
            },
        }
        rules.append(rule)
    return rules
