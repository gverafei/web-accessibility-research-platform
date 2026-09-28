# Tests and verification

Verification should match the change's risk. Documentation builds do not make paid calls; web/evaluator tests use controlled fixtures where possible. Live-site behavior needs a separate bounded pilot.

## Web suite

From a Python environment with the web requirements installed:

```bash
pybabel compile -d web/app/translations
python -m unittest discover -s web/tests -q
git diff --check
```

For the Docker environment, mount the repository at `/workspace` so the suite sees current tests rather than a stale container copy:

```bash
docker compose run --rm --no-deps \
  --volume "$PWD:/workspace:ro" --workdir /workspace \
  web sh -c 'pybabel compile -d /app/translations && python -m unittest discover -s web/tests -q'
```

This creates a one-off **web test container**, not another remediation worker. Build the web image first if needed. Review the tests before running them against important live research state.

## Evaluator and extension

```bash
docker compose exec evaluator npm test
node --test browser_extension/tests/*.test.cjs
node --test web/tests/*.cjs
```

Browser controls still need a real UI check after reloading the extension. A mocked API test alone does not verify a side panel in every Chromium-derived browser.

## Remediation test coverage

The remediation suites cover source preservation, usage accounting, evaluator errors, candidate selection and rollback, tool/skill versions and retrieval evidence. They also exercise catalogue validation, reasoning controls, unavailable providers, malformed operations, budget stops and frozen target settings. Model responses in regression tests use controlled fixtures.

## Documentation checks

```bash
python -m pip install -r requirements-docs.txt
python docs/tools/check_examples.py
mkdocs build --strict
python docs/tools/check_site.py
```

The example checker validates Python/JSON syntax, shell syntax, marked offline examples and source references. The site checker verifies generated local links, anchors and the search index. Provider connectivity and live-site acquisition are checked separately.

## Visual and behavioral QA

Preview the site/report in a real browser. Check left navigation, search, light/dark mode, narrow layouts, keyboard focus, code copy controls, chart legends and thumbnail loading. When checking scientific figures, inspect rendered output rather than only successful compilation.

Job diagnostics combine container health with committed progress and event records. Offline recovery tests exercise retry, interruption and reserve-exhaustion paths without submitting a live cohort.
