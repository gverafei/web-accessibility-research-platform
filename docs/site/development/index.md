# Development environment

The repository contains the Flask application, Node evaluator, dataset server, browser extension, tests and software documentation.

## Source layout

```text
web/app/                 Flask routes, settings, jobs and remediation modules
web/tests/               Python and JavaScript verification
evaluator/               Browser/tool service and Node tests
dataset_server/          Internal HTML/resource server
browser_extension/       Chromium side panel and background worker
docs/site/               Published user/developer documentation
docs/tools/              Documentation verification helpers
docker-compose.yml       Service topology and local builds
```

The site's configured source is `docs/site`; generated files are ignored under `site/`.

## Build from source

```bash
cp .env.example .env
docker compose up -d --build
```

The single Compose file mounts `web/app` into the web and worker containers. It does not mount evaluator source: rebuild that image after evaluator changes. A worker process already running Python does not necessarily reload changed code. Coordinate a safe pause/restart before applying runtime changes to an ongoing study. Never interrupt paid or long-running work merely to inspect a template.

For changes to image dependencies or Dockerfiles, rebuild the affected service. Browser extension changes require its separate browser reload action.

## Local Python tooling

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r web/requirements.txt
pybabel compile -d web/app/translations
```

Tests often provide controlled mocks and fixtures; importing `main.py` initializes the application/database. Do not import it merely to call a pure helper in an offline example. Prefer module-level contracts such as `automatic_recipe`, `sample_tranco` and `ToolRegistry`.

## Change discipline

Acceptance, budgets and rollback are deterministic parts of the runtime. Model output is validated as untrusted data, and tool/skill versions are retained in each run's evidence. Changes to these contracts need regression tests, including source immutability and retention of the best evaluated candidate.

Behavioral claims need a bounded pilot or ablation in addition to unit tests. A stochastic result from one page is exploratory evidence, not a model ranking.

## Contribution workflow

1. Create a focused branch and reproduce the behavior safely.
2. Add a regression test and implement the smallest coherent fix.
3. Run the relevant suite, then the full web suite for application changes.
4. Run `git diff --check` and inspect staged files for secrets/generated artifacts.
5. Update the affected documentation and verify its build.
6. Explain the changed behavior, evidence and migration implications in the review.

See [testing](testing.md), [extension points](extending.md) and the [source map](../reference/source-map.md).
