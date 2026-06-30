"""Assemble a complete Grafana dashboard from a spec.

Responsibilities:

* lay panels out on the 24-column grid, grouping them under collapsible rows;
* build the templating list (datasource + custom variables);
* emit the portable ``__inputs`` / ``__requires`` envelope so the JSON imports
  cleanly into any Grafana with the operator selecting the datasource;
* attach a standard annotations list and sensible time/refresh defaults.

The output is deterministic: identical input always yields byte-identical JSON,
which keeps diffs meaningful and CI reproducible.
"""

from __future__ import annotations

import json
from typing import Any

from .panels import build_panel, ds_ref

SCHEMA_VERSION = 39
GRID_WIDTH = 24
DEFAULT_PANEL_HEIGHT = 8
ROW_HEIGHT = 1


def _grafana_version() -> str:
    return "11.1.0"


def _input_for(ds_kind: str) -> dict[str, Any]:
    meta = {
        "prometheus": ("DS_PROMETHEUS", "Prometheus", "prometheus", "Prometheus"),
        "loki": ("DS_LOKI", "Loki", "loki", "Loki"),
    }[ds_kind]
    return {"name": meta[0], "label": meta[1], "description": "", "type": "datasource", "pluginId": meta[2], "pluginName": meta[3]}


def _requires(ds_kinds: set[str]) -> list[dict[str, Any]]:
    req = [{"type": "grafana", "id": "grafana", "name": "Grafana", "version": _grafana_version()}]
    plugin_meta = {
        "prometheus": ("prometheus", "Prometheus", "1.0.0"),
        "loki": ("loki", "Loki", "1.0.0"),
    }
    for kind in sorted(ds_kinds):
        pid, pname, pver = plugin_meta[kind]
        req.append({"type": "datasource", "id": pid, "name": pname, "version": pver})
    return req


def _annotations(ds_kind: str) -> dict[str, Any]:
    return {
        "list": [
            {
                "builtIn": 1,
                "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                "enable": True,
                "hide": True,
                "iconColor": "rgba(0, 211, 255, 1)",
                "name": "Annotations & Alerts",
                "type": "dashboard",
            }
        ]
    }


def _templating(spec: dict[str, Any], ds_kind: str) -> dict[str, Any]:
    variables: list[dict[str, Any]] = []
    for var in spec.get("templating", []):
        vtype = var.get("type", "query")
        base = {
            "name": var["name"],
            "label": var.get("label", var["name"]),
            "type": vtype,
            "hide": {"label": 0, "variable": 0, "": 0}.get(var.get("hide", ""), 0) if isinstance(var.get("hide"), str) else var.get("hide", 0),
            "description": var.get("description", None),
        }
        if vtype == "query":
            base.update({
                "datasource": ds_ref(var.get("datasource", ds_kind)),
                "definition": var["query"],
                "query": {"qryType": 1, "query": var["query"], "refId": "variable"},
                "refresh": var.get("refresh", 2),
                "regex": var.get("regex", ""),
                "sort": var.get("sort", 1),
                "includeAll": var.get("includeAll", True),
                "allValue": var.get("allValue", ".*"),
                "multi": var.get("multi", True),
                "current": {},
                "options": [],
            })
        elif vtype == "custom":
            opts = var["options"]
            base.update({
                "query": ",".join(opts),
                "includeAll": var.get("includeAll", False),
                "multi": var.get("multi", False),
                "current": {"text": opts[0], "value": opts[0]},
                "options": [{"text": o, "value": o, "selected": i == 0} for i, o in enumerate(opts)],
            })
        elif vtype == "interval":
            opts = var.get("options", ["1m", "5m", "10m", "30m", "1h", "6h", "12h", "1d"])
            base.update({
                "query": ",".join(opts),
                "auto": var.get("auto", True),
                "auto_count": var.get("auto_count", 30),
                "auto_min": var.get("auto_min", "10s"),
                "current": {"text": opts[0], "value": opts[0]},
                "options": [{"text": o, "value": o, "selected": i == 0} for i, o in enumerate(opts)],
                "refresh": 2,
            })
        elif vtype == "constant":
            base.update({"query": var["value"], "current": {"value": var["value"], "text": var["value"]}, "hide": 2})
        elif vtype == "textbox":
            base.update({"query": var.get("default", ""), "current": {"text": var.get("default", ""), "value": var.get("default", "")}, "options": []})
        variables.append(base)
    return {"list": variables}


def _layout(rows: list[dict[str, Any]], ds_kind: str) -> list[dict[str, Any]]:
    """Place panels on the grid, one collapsible row per section."""
    panels: list[dict[str, Any]] = []
    pid = 1
    y = 0
    for section in rows:
        # Row header panel.
        panels.append({
            "id": pid,
            "type": "row",
            "title": section.get("title", ""),
            "collapsed": False,
            "gridPos": {"h": ROW_HEIGHT, "w": GRID_WIDTH, "x": 0, "y": y},
            "panels": [],
        })
        pid += 1
        y += ROW_HEIGHT

        sub = section.get("panels", [])
        n = len(sub)
        x = 0
        row_y = y
        max_h = 0
        for ps in sub:
            built = build_panel(ps, ps.get("datasource", ds_kind))
            w = ps.get("width") or max(4, GRID_WIDTH // max(1, n))
            w = min(w, GRID_WIDTH)
            h = ps.get("height", DEFAULT_PANEL_HEIGHT)
            if x + w > GRID_WIDTH:
                x = 0
                row_y += max_h
                max_h = 0
            built["id"] = pid
            built["gridPos"] = {"h": h, "w": w, "x": x, "y": row_y}
            pid += 1
            panels.append(built)
            x += w
            max_h = max(max_h, h)
        y = row_y + (max_h if max_h else 0)
    return panels


def _datasource_kinds(spec: dict[str, Any]) -> set[str]:
    kinds = {spec.get("datasource", "prometheus")}
    for section in spec.get("rows", []):
        for p in section.get("panels", []):
            if "datasource" in p:
                kinds.add(p["datasource"])
    for v in spec.get("templating", []):
        if v.get("type", "query") == "query":
            kinds.add(v.get("datasource", spec.get("datasource", "prometheus")))
    return kinds


def build_dashboard(spec: dict[str, Any]) -> dict[str, Any]:
    """Compile a spec dict into a complete, importable Grafana dashboard dict."""
    ds_kind = spec.get("datasource", "prometheus")
    ds_kinds = _datasource_kinds(spec)
    panels = _layout(spec.get("rows", []), ds_kind)

    dashboard = {
        "__inputs": [_input_for(k) for k in sorted(ds_kinds)],
        "__requires": _requires(ds_kinds),
        "annotations": _annotations(ds_kind),
        "description": spec.get("description", ""),
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": spec.get("graphTooltip", 1),
        "id": None,
        "links": [],
        "liveNow": False,
        "panels": panels,
        "refresh": spec.get("refresh", "30s"),
        "schemaVersion": SCHEMA_VERSION,
        "tags": spec.get("tags", []),
        "templating": _templating(spec, ds_kind),
        "time": {"from": spec.get("time_from", "now-6h"), "to": spec.get("time_to", "now")},
        "timepicker": {},
        "timezone": spec.get("timezone", ""),
        "title": spec["title"],
        "uid": spec["uid"],
        "version": 1,
        "weekStart": "",
    }
    return dashboard


def to_json(dashboard: dict[str, Any]) -> str:
    """Serialise deterministically with a trailing newline."""
    return json.dumps(dashboard, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
