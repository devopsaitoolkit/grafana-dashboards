"""Strict validator for generated dashboards and alert rules.

This is the project's quality gate (it stands in for grafana/dashboard-linter,
which needs a Go toolchain). It fails the build on any hard error and prints a
summary of warnings.

Hard invariants enforced:

* every ``dashboards/**.json`` is valid JSON with the required envelope;
* ``schemaVersion`` is current and ``uid`` is unique, lowercase-kebab, <= 40 chars;
* every non-row panel has a non-empty title, a ``${DS_...}`` datasource reference
  and at least one target with a non-empty ``expr`` (Loki panels may use logs);
* single-value panels (stat/gauge/bargauge) declare a unit;
* **no URLs and no "devopsaitoolkit" appear anywhere in dashboard JSON** — promo
  links and hardcoded datasource URLs are both forbidden in dashboards;
* panel ids are unique and gridPos stays within the 24-column grid;
* alert rules carry a severity and a summary.

Usage::

    python -m dashgen.validate          # validate the whole repo
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DASHBOARDS = ROOT / "dashboards"
ALERTS = ROOT / "alerts"

UID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
DS_RE = re.compile(r"^\$\{DS_[A-Z0-9_]+\}$")
URL_RE = re.compile(r"https?://")
SINGLE_VALUE = {"stat", "gauge", "bargauge"}
CURRENT_SCHEMA = 39


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


def _check_panel(panel: dict, where: str, ds_inputs: set[str], rep: Report, ids: set) -> None:
    ptype = panel.get("type")
    if ptype == "row":
        return
    pid = panel.get("id")
    if pid in ids:
        rep.err(where, f"duplicate panel id {pid}")
    ids.add(pid)

    title = panel.get("title", "")
    if not title.strip() and ptype != "text":
        rep.err(where, f"panel id {pid} has empty title")

    gp = panel.get("gridPos", {})
    if gp.get("x", 0) + gp.get("w", 0) > 24:
        rep.err(where, f"panel {title!r} overflows grid (x+w>24)")

    if ptype == "text":
        return

    ds = panel.get("datasource", {})
    uid = ds.get("uid", "")
    if not DS_RE.match(uid):
        rep.err(where, f"panel {title!r} datasource uid {uid!r} is not a ${{DS_*}} input")
    else:
        ds_inputs.add(uid)

    targets = panel.get("targets", [])
    real = [t for t in targets if t.get("expr", "").strip()]
    if not real:
        rep.err(where, f"panel {title!r} has no target with a non-empty expr")

    defaults = panel.get("fieldConfig", {}).get("defaults", {})
    if ptype in SINGLE_VALUE and not defaults.get("unit"):
        rep.err(where, f"single-value panel {title!r} ({ptype}) is missing a unit")
    if ptype == "timeseries" and not defaults.get("unit"):
        rep.warn(where, f"timeseries panel {title!r} has no unit")


def validate_dashboards(rep: Report) -> int:
    uids: dict[str, str] = {}
    files = sorted(DASHBOARDS.rglob("*.json"))
    for f in files:
        where = f.relative_to(ROOT).as_posix()
        raw = f.read_text(encoding="utf-8")
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as e:
            rep.err(where, f"invalid JSON: {e}")
            continue

        # Hard invariant: no URLs / promo strings anywhere in the JSON.
        if URL_RE.search(raw):
            for m in set(URL_RE.findall(raw)):
                rep.err(where, "contains a URL (forbidden in dashboard JSON)")
                break
        if "devopsaitoolkit" in raw.lower():
            rep.err(where, "contains 'devopsaitoolkit' (no promo in dashboard JSON)")

        for key in ("schemaVersion", "panels", "templating", "title", "uid", "__inputs", "__requires"):
            if key not in d:
                rep.err(where, f"missing top-level key {key!r}")
        if d.get("schemaVersion") != CURRENT_SCHEMA:
            rep.err(where, f"schemaVersion {d.get('schemaVersion')} != {CURRENT_SCHEMA}")

        uid = d.get("uid", "")
        if not UID_RE.match(uid):
            rep.err(where, f"uid {uid!r} not lowercase-kebab <=40 chars")
        if uid in uids:
            rep.err(where, f"duplicate uid {uid!r} (also in {uids[uid]})")
        uids[uid] = where

        if not d.get("tags"):
            rep.warn(where, "no tags")

        # Path/uid should align with the folder for discoverability.
        ds_inputs: set[str] = set()
        ids: set = set()
        for panel in d.get("panels", []):
            _check_panel(panel, where, ds_inputs, rep, ids)
            for sub in panel.get("panels", []):
                _check_panel(sub, where, ds_inputs, rep, ids)

        declared = {i["name"] for i in d.get("__inputs", [])}
        used = {u.strip("${}") for u in ds_inputs}
        missing = used - declared
        if missing:
            rep.err(where, f"datasource inputs used but not declared: {sorted(missing)}")

    return len(files)


def validate_alerts(rep: Report) -> int:
    count = 0
    for f in sorted(ALERTS.rglob("*.yml")):
        where = f.relative_to(ROOT).as_posix()
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            rep.err(where, f"invalid YAML: {e}")
            continue
        for group in doc.get("groups", []):
            for rule in group.get("rules", []):
                count += 1
                name = rule.get("alert", "?")
                if not rule.get("expr", "").strip():
                    rep.err(where, f"alert {name!r} has empty expr")
                if not rule.get("labels", {}).get("severity"):
                    rep.err(where, f"alert {name!r} missing labels.severity")
                if not rule.get("annotations", {}).get("summary"):
                    rep.err(where, f"alert {name!r} missing annotations.summary")
    return count


def main() -> int:
    rep = Report()
    n_dash = validate_dashboards(rep)
    n_alerts = validate_alerts(rep)

    for w in rep.warnings:
        print(f"  WARN  {w}")
    for e in rep.errors:
        print(f"  ERROR {e}")

    print(f"\nvalidate: {n_dash} dashboards, {n_alerts} alert rules — "
          f"{len(rep.errors)} errors, {len(rep.warnings)} warnings")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
