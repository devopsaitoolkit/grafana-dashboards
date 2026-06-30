"""Panel builders.

Each builder turns a compact panel spec (a dict from YAML) into a complete
Grafana panel object. ``gridPos`` and ``id`` are assigned later by the layout
engine in :mod:`dashgen.dashboard`, so builders here never set position.

All Prometheus/Loki targets reference the datasource by template input
(``${DS_PROMETHEUS}`` / ``${DS_LOKI}``) so the exported JSON is portable: on
import Grafana prompts the operator to bind a concrete datasource. No real
datasource UIDs, URLs, org names or credentials are ever emitted.
"""

from __future__ import annotations

from typing import Any

# Grafana panel `type` for each spec `type`.
PANEL_TYPES = {
    "timeseries": "timeseries",
    "stat": "stat",
    "gauge": "gauge",
    "bargauge": "bargauge",
    "table": "table",
    "heatmap": "heatmap",
    "piechart": "piechart",
    "logs": "logs",
    "state-timeline": "state-timeline",
    "text": "text",
}

# Panel types that don't query a datasource.
NO_TARGET_TYPES = {"text"}

# Default thresholds when a spec omits them (green base only).
_DEFAULT_THRESHOLDS = [{"color": "green", "value": None}]


def ds_ref(kind: str) -> dict[str, str]:
    """Return a datasource reference using the portable template input."""
    inputs = {"prometheus": "${DS_PROMETHEUS}", "loki": "${DS_LOKI}"}
    plugin = {"prometheus": "prometheus", "loki": "loki"}
    return {"type": plugin[kind], "uid": inputs[kind]}


def _thresholds(spec: dict[str, Any]) -> dict[str, Any]:
    steps = []
    for s in spec.get("thresholds", _DEFAULT_THRESHOLDS):
        steps.append({"color": s["color"], "value": s.get("value")})
    if not steps or steps[0].get("value") is not None:
        steps.insert(0, {"color": "green", "value": None})
    return {"mode": "absolute", "steps": steps}


def _color(spec: dict[str, Any]) -> dict[str, Any]:
    mode = spec.get("color", "palette-classic" if spec["type"] == "timeseries" else "thresholds")
    out: dict[str, Any] = {"mode": mode}
    if mode == "fixed" and spec.get("fixedColor"):
        out["fixedColor"] = spec["fixedColor"]
    return out


def _targets(spec: dict[str, Any], ds_kind: str) -> list[dict[str, Any]]:
    targets = []
    ds = ds_ref(ds_kind)
    for i, t in enumerate(spec.get("targets", [])):
        ref_id = t.get("refId", chr(ord("A") + i))
        if ds_kind == "loki":
            target = {
                "datasource": ds,
                "editorMode": "code",
                "expr": t["expr"],
                "queryType": t.get("queryType", "range"),
                "refId": ref_id,
            }
            if t.get("legend"):
                target["legendFormat"] = t["legend"]
        else:
            target = {
                "datasource": ds,
                "editorMode": "code",
                "expr": t["expr"],
                "instant": bool(t.get("instant", False)),
                "range": not bool(t.get("instant", False)),
                "legendFormat": t.get("legend", "__auto"),
                "refId": ref_id,
            }
            if t.get("format"):
                target["format"] = t["format"]
        targets.append(target)
    return targets


def _field_config(spec: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "color": _color(spec),
        "mappings": spec.get("mappings", []),
        "thresholds": _thresholds(spec),
    }
    if "unit" in spec:
        defaults["unit"] = spec["unit"]
    if "min" in spec:
        defaults["min"] = spec["min"]
    if "max" in spec:
        defaults["max"] = spec["max"]
    if "decimals" in spec:
        defaults["decimals"] = spec["decimals"]
    if "noValue" in spec:
        defaults["noValue"] = spec["noValue"]
    if custom:
        defaults["custom"] = custom
    overrides = spec.get("overrides", [])
    return {"defaults": defaults, "overrides": overrides}


def _legend(spec: dict[str, Any]) -> dict[str, Any]:
    mode = spec.get("legend", "list")
    if mode == "hidden":
        return {"showLegend": False, "displayMode": "list", "placement": "bottom", "calcs": []}
    calcs = spec.get("legend_calcs", ["lastNotNull", "max", "mean"] if mode == "table" else [])
    return {
        "showLegend": True,
        "displayMode": mode,
        "placement": spec.get("legend_placement", "bottom"),
        "calcs": calcs,
    }


def _tooltip(spec: dict[str, Any]) -> dict[str, Any]:
    return {"mode": spec.get("tooltip", "multi"), "sort": spec.get("tooltip_sort", "desc")}


# --- individual builders -------------------------------------------------------


def _build_timeseries(spec, ds_kind):
    custom = {
        "drawStyle": spec.get("drawStyle", "line"),
        "lineInterpolation": spec.get("lineInterpolation", "linear"),
        "lineWidth": spec.get("lineWidth", 1),
        "fillOpacity": spec.get("fillOpacity", 10),
        "gradientMode": spec.get("gradientMode", "none"),
        "spanNulls": spec.get("spanNulls", False),
        "showPoints": spec.get("showPoints", "never"),
        "pointSize": 5,
        "stacking": {"mode": spec.get("stacking", "none"), "group": "A"},
        "axisPlacement": spec.get("axisPlacement", "auto"),
        "axisLabel": spec.get("axisLabel", ""),
        "scaleDistribution": {"type": spec.get("scale", "linear")},
        "axisCenteredZero": False,
        "hideFrom": {"tooltip": False, "viz": False, "legend": False},
        "thresholdsStyle": {"mode": spec.get("thresholdsStyle", "off")},
    }
    return {
        "fieldConfig": _field_config(spec, custom),
        "options": {"legend": _legend(spec), "tooltip": _tooltip(spec)},
    }


def _build_stat(spec, ds_kind):
    return {
        "fieldConfig": _field_config(spec, {}),
        "options": {
            "reduceOptions": {
                "calcs": [spec.get("calc", "lastNotNull")],
                "fields": spec.get("fields", ""),
                "values": False,
            },
            "orientation": spec.get("orientation", "auto"),
            "textMode": spec.get("textMode", "auto"),
            "colorMode": spec.get("colorMode", "value"),
            "graphMode": spec.get("graphMode", "area"),
            "justifyMode": "auto",
            "showPercentChange": False,
        },
    }


def _build_gauge(spec, ds_kind):
    return {
        "fieldConfig": _field_config(spec, {}),
        "options": {
            "reduceOptions": {"calcs": [spec.get("calc", "lastNotNull")], "fields": "", "values": False},
            "orientation": "auto",
            "showThresholdLabels": spec.get("showThresholdLabels", False),
            "showThresholdMarkers": True,
        },
    }


def _build_bargauge(spec, ds_kind):
    return {
        "fieldConfig": _field_config(spec, {}),
        "options": {
            "reduceOptions": {"calcs": [spec.get("calc", "lastNotNull")], "fields": "", "values": False},
            "orientation": spec.get("orientation", "horizontal"),
            "displayMode": spec.get("displayMode", "gradient"),
            "valueMode": "color",
            "showUnfilled": True,
            "minVizWidth": 0,
            "minVizHeight": 10,
        },
    }


def _build_table(spec, ds_kind):
    custom = {
        "align": "auto",
        "cellOptions": {"type": spec.get("cellType", "auto")},
        "inspect": False,
        "filterable": spec.get("filterable", True),
    }
    return {
        "fieldConfig": _field_config(spec, custom),
        "options": {
            "showHeader": True,
            "cellHeight": "sm",
            "footer": {"show": False, "reducer": ["sum"], "countRows": False, "fields": ""},
            "sortBy": spec.get("sortBy", []),
        },
    }


def _build_heatmap(spec, ds_kind):
    return {
        "fieldConfig": {"defaults": {"custom": {"scaleDistribution": {"type": "linear"}}}, "overrides": []},
        "options": {
            "calculate": spec.get("calculate", False),
            "cellGap": 1,
            "color": {"scheme": "Spectral", "mode": "scheme", "steps": 64, "reverse": False, "exponent": 0.5},
            "yAxis": {"unit": spec.get("unit", "short"), "axisPlacement": "left"},
            "tooltip": {"mode": "single", "yHistogram": False, "showColorScale": True},
            "legend": {"show": True},
            "exemplars": {"color": "rgba(255,0,255,0.7)"},
            "filterValues": {"le": 1e-9},
            "rowsFrame": {"layout": "auto"},
            "cellValues": {},
        },
    }


def _build_piechart(spec, ds_kind):
    return {
        "fieldConfig": _field_config(spec, {}),
        "options": {
            "reduceOptions": {"calcs": [spec.get("calc", "lastNotNull")], "fields": "", "values": False},
            "pieType": spec.get("pieType", "donut"),
            "tooltip": {"mode": "single", "sort": "none"},
            "legend": {"showLegend": True, "displayMode": "list", "placement": "right", "values": ["percent"]},
            "displayLabels": ["name"],
        },
    }


def _build_logs(spec, ds_kind):
    return {
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {
            "showTime": True,
            "showLabels": False,
            "showCommonLabels": False,
            "wrapLogMessage": True,
            "prettifyLogMessage": False,
            "enableLogDetails": True,
            "dedupStrategy": "none",
            "sortOrder": spec.get("sortOrder", "Descending"),
        },
    }


def _build_state_timeline(spec, ds_kind):
    custom = {"lineWidth": 0, "fillOpacity": 80, "spanNulls": False, "insertNulls": False, "hideFrom": {"tooltip": False, "viz": False, "legend": False}}
    return {
        "fieldConfig": _field_config(spec, custom),
        "options": {
            "mergeValues": True,
            "showValue": spec.get("showValue", "auto"),
            "alignValue": "left",
            "rowHeight": 0.9,
            "legend": _legend(spec),
            "tooltip": {"mode": "single", "sort": "none"},
        },
    }


def _build_text(spec, ds_kind):
    return {
        "options": {"mode": spec.get("mode", "markdown"), "content": spec.get("content", ""), "code": {"language": "plaintext", "showLineNumbers": False, "showMiniMap": False}},
        "fieldConfig": {"defaults": {}, "overrides": []},
    }


_BUILDERS = {
    "timeseries": _build_timeseries,
    "stat": _build_stat,
    "gauge": _build_gauge,
    "bargauge": _build_bargauge,
    "table": _build_table,
    "heatmap": _build_heatmap,
    "piechart": _build_piechart,
    "logs": _build_logs,
    "state-timeline": _build_state_timeline,
    "text": _build_text,
}


def build_panel(spec: dict[str, Any], ds_kind: str) -> dict[str, Any]:
    """Build one Grafana panel from a spec dict (no gridPos/id yet)."""
    ptype = spec["type"]
    if ptype not in _BUILDERS:
        raise ValueError(f"unknown panel type: {ptype!r}")
    panel: dict[str, Any] = {
        "type": PANEL_TYPES[ptype],
        "title": spec.get("title", ""),
    }
    if spec.get("description"):
        panel["description"] = spec["description"]
    body = _BUILDERS[ptype](spec, ds_kind)
    panel.update(body)
    if ptype not in NO_TARGET_TYPES:
        panel["datasource"] = ds_ref(ds_kind)
        panel["targets"] = _targets(spec, ds_kind)
    if spec.get("transformations"):
        panel["transformations"] = spec["transformations"]
    if "repeat" in spec:
        panel["repeat"] = spec["repeat"]
        panel["repeatDirection"] = spec.get("repeatDirection", "h")
    return panel
