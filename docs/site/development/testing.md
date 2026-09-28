# Tests and verification

Verification should match the change's risk. Documentation builds do not make paid calls; web/evaluator tests use controlled fixtures where possible. Live-site behavior needs a separate bounded pilot.

## Web suite

From a Python environment with the web requirements installed:

```bash
pybabel compile -d web/app/translations
python -m unittest discover -s web/tests -q
git diff --check
```

For the Docker development environment, mount the repository at `/workspace` so the suite sees current tests rather than a stale container copy:

```bash
docker compose -f docker-compose-dev.yml run --rm --no-deps \
  --volume "$PWD:/workspace:ro" --workdir /workspace \
  web sh -c 'pybabel compile -d /app/translations && python -m unittest discover -s web/tests -q'
```

This creates a one-off **web test container**, not another remediation worker. It assumes the normal development services are available for any application setup needed by the tests. Review the tests before running them against important live research state.

## Evaluator and extension

```bash
docker compose -f docker-compose-dev.yml exec evaluator npm test
node --test browser_extension/tests/*.test.cjs
node --test web/tests/*.cjs
```

Browser controls still need a real UI check after reloading the extension. A mocked API test alone does not verify a side panel in every Chromium-derived browser.

## Required remediation checks

For remediation changes, verify at minimum:

1. The stored source remains immutable.
2. Paid calls are recorded before output parsing can fail.
3. Incomplete evaluator responses keep their original error.
4. Regressions retain the best evaluated candidate.
5. The iteration report shows actual skill/tool versions and RAG usage.

Also test invalid/missing catalogue choices, unsupported reasoning, unavailable local providers, malformed operations, budget stops and target configuration freezing. Never use a real paid request as an unbounded regression test.

## Documentation checks

```bash
python -m pip install -r requirements-docs.txt
python docs/tools/check_examples.py
mkdocs build --strict
python docs/tools/check_site.py
```

The example checker validates Python/JSON syntax, shell syntax and explicitly marked offline examples. It also checks source references maintained in the source map. The site checker verifies local HTML links/anchors and the search index. These checks do not claim every provider, public website or external link is available.

## Visual and behavioral QA

Preview the site/report in a real browser. Check left navigation, search, light/dark mode, narrow layouts, keyboard focus, code copy controls, chart legends and thumbnail loading. When checking scientific figures, inspect rendered output rather than only successful compilation.

For job fixes, verify committed progress before/after a meaningful observation boundary. Container health alone is not evidence that a job advances. Do not duplicate a job or paid cohort to test a recovery fix.
