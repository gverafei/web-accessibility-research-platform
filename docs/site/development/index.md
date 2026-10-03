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

The single Compose file mounts `web/app` into the web and worker containers.
Evaluator changes require rebuilding its image. Python worker changes take
effect after restarting that service; pause active work before a runtime update.
The web service uses Gunicorn, so restart `web` after Python or cached-template
changes even though the files are mounted. CSS/JavaScript may also need a browser
reload or updated asset version. Recompile translations before serving changed
messages (the normal web startup does this).

For changes to image dependencies or Dockerfiles, rebuild the affected service. Browser extension changes require its separate browser reload action.

## Local Python tooling

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r web/requirements.txt
pybabel compile -d web/app/translations
```

Tests use controlled mocks and fixtures. Importing `main.py` initializes the application and database, while helper modules such as `automatic_recipe`, `sample_tranco` and `ToolRegistry` can be exercised independently.

## Runtime integration

The worker coordinates acquisition and remediation through typed tool interfaces. Settings and run snapshots supply the experiment controls, while iteration records connect generated candidates with measurements and selection decisions. The [runtime reference](../technical/agent-runtime.md) describes these interfaces, and the [testing guide](testing.md) lists the available suites.

## Contribution workflow

1. Create a focused branch and reproduce the behavior safely.
2. Add a regression test and implement the smallest coherent fix.
3. Run the relevant suite, then the full web suite for application changes.
4. Run `git diff --check` and inspect staged files for secrets/generated artifacts.
5. Update the affected documentation and verify its build.
6. Explain the changed behavior, evidence and migration implications in the review.

See [testing](testing.md), [extension points](extending.md) and the [source map](../reference/source-map.md).
