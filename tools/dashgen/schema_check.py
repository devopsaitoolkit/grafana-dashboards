"""Validate every generated dashboard against a JSON Schema.

This complements ``validate.py`` (which does semantic/operational checks) with a
structural contract: the keys and types Grafana expects in an importable
dashboard. Uses the ``jsonschema`` library.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]

DASHBOARD_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["__inputs", "__requires", "schemaVersion", "title", "uid",
                 "panels", "templating", "annotations", "time", "tags"],
    "properties": {
        "schemaVersion": {"type": "integer", "minimum": 36},
        "title": {"type": "string", "minLength": 1},
        "uid": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{1,39}$"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "refresh": {"type": "string"},
        "__inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type", "pluginId"],
                "properties": {
                    "name": {"type": "string", "pattern": "^DS_[A-Z0-9_]+$"},
                    "type": {"const": "datasource"},
                },
            },
        },
        "templating": {
            "type": "object",
            "required": ["list"],
            "properties": {"list": {"type": "array"}},
        },
        "annotations": {
            "type": "object",
            "required": ["list"],
            "properties": {"list": {"type": "array", "minItems": 1}},
        },
        "time": {
            "type": "object",
            "required": ["from", "to"],
        },
        "panels": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["type", "gridPos", "id"],
                "properties": {
                    "type": {"type": "string"},
                    "id": {"type": "integer"},
                    "gridPos": {
                        "type": "object",
                        "required": ["h", "w", "x", "y"],
                        "properties": {
                            "h": {"type": "integer", "minimum": 1},
                            "w": {"type": "integer", "minimum": 1, "maximum": 24},
                            "x": {"type": "integer", "minimum": 0, "maximum": 23},
                            "y": {"type": "integer", "minimum": 0},
                        },
                    },
                },
            },
        },
    },
}


def main() -> int:
    validator = Draft202012Validator(DASHBOARD_SCHEMA)
    files = sorted((ROOT / "dashboards").rglob("*.json"))
    errors = 0
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        for err in validator.iter_errors(d):
            path = "/".join(str(p) for p in err.path)
            print(f"  ERROR {f.relative_to(ROOT)} :: {path}: {err.message}")
            errors += 1
    print(f"\nschema_check: {len(files)} dashboards, {errors} schema errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
