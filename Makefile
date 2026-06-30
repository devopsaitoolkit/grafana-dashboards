# grafana-dashboards — build and validation entry points.
#
#   make build     compile every spec in tools/specs/ into dashboards/, docs/,
#                  screenshots/ and alerts/
#   make validate  run the strict dashboard + alert validator
#   make check     build, then fail if anything is out of date (CI uses this)
#   make fmt       canonicalise all dashboard JSON formatting
#   make clean     remove generated dashboards/docs/screenshots/alerts

PY ?= python3

.PHONY: build validate check fmt lint clean help

help:
	@grep -E '^#   ' Makefile | sed 's/^#   //'

build:
	$(PY) -m tools.dashgen.build

validate:
	$(PY) -m tools.dashgen.validate

# Build into the working tree, then ensure the committed output matches.
check: build validate
	@git diff --exit-code -- dashboards docs screenshots alerts assets \
		|| { echo "ERROR: generated files are out of date — run 'make build' and commit."; exit 1; }

fmt:
	$(PY) -m tools.dashgen.build --quiet

clean:
	rm -rf dashboards/*/ docs/dashboards/ screenshots/*/ alerts/*.rules.yml assets/catalog.json docs/catalog.md
