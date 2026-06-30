# Security Policy

## Scope

This repository contains Grafana dashboard JSON, Prometheus alert/recording rules,
documentation, and a Python generator. It ships **no runtime service** and contains
**no secrets**. The most relevant security concerns are therefore:

- **Never commit credentials.** Dashboards reference datasources via `${DS_*}`
  inputs, never URLs or tokens. The validator (`make validate`) fails the build if
  a URL appears in any dashboard JSON. The helper scripts read Grafana URLs/tokens
  from environment variables only.
- **PromQL safety.** Queries are read-only by nature. The diagnostic scripts only
  call read endpoints except for the explicit `import`/`restore` commands.

## Reporting a vulnerability

If you find a security issue (for example, a script that could leak a token, or a
supply-chain concern in the tooling):

1. **Do not** open a public issue.
2. Use GitHub's **private vulnerability reporting** ("Report a vulnerability" under
   the Security tab) for this repository.
3. Include reproduction steps and the affected file(s).

We aim to acknowledge reports within **5 business days** and to provide a fix or
mitigation timeline after triage.

## Supported versions

The `main` branch is the supported version. Tagged releases are snapshots of the
dashboard library at a point in time.
