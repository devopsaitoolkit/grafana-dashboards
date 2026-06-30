"""dashgen — compile compact dashboard specs into production-ready Grafana JSON.

The library is deliberately small and dependency-light (PyYAML only). It exists so
that 100+ dashboards share one consistent, schema-correct foundation: identical
templating, units, thresholds, legends and datasource handling, with the
operational content (which panels, which PromQL, which thresholds) living in
human-readable YAML specs under ``tools/specs/``.

Public entry points:

* :func:`dashgen.dashboard.build_dashboard` — spec dict -> Grafana dashboard dict
* :mod:`dashgen.build` — CLI that compiles every spec to ``dashboards/**.json``
* :mod:`dashgen.validate` — strict validator for the generated JSON
"""

__version__ = "1.0.0"
