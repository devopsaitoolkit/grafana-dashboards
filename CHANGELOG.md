# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial public release of the dashboard library.
- Spec-driven generator (`tools/dashgen`) producing Grafana dashboard JSON,
  documentation pages, annotated SVG screenshots, and Prometheus alert rules.
- 100+ production-ready dashboards across Linux, Kubernetes, Docker, OpenStack
  (Nova, Neutron, Cinder, Glance, Keystone, RabbitMQ, MariaDB, HAProxy, Placement,
  Heat, Horizon, OVS), the monitoring stack (Prometheus, Alertmanager,
  VictoriaMetrics, Mimir, Loki, Tempo), databases (PostgreSQL, MySQL, Redis),
  web servers (NGINX, Apache), and cloud (VMware, AWS, Azure, GCP).
- PromQL cookbook, dashboard catalog, compatibility matrix, troubleshooting
  flowchart, and observability learning path.
- Recording rules, datasource provisioning examples, and helper scripts
  (validate, import, export, format, backup, restore, diff, provision, screenshot).
- CI: build + strict validation + JSON Schema + YAML lint + markdown/spell/link checks.
