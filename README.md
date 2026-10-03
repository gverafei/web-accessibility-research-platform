# A11yResearch: Web Accessibility Research Platform

A11yResearch helps researchers acquire and evaluate collections of web pages, remediate accessibility barriers with explicit AI controls, and compare original and repaired pages while retaining reproducible evidence.

**[Complete documentation](https://gverafei.github.io/web-accessibility-research-platform/)** · [Installation](https://gverafei.github.io/web-accessibility-research-platform/getting-started/installation/) · [Researcher guide](https://gverafei.github.io/web-accessibility-research-platform/guide/acquisition/) · [Technical architecture](https://gverafei.github.io/web-accessibility-research-platform/technical/architecture/)

## Features

- Public-URL acquisition, seeded Tranco sampling and local HTML datasets.
- Axe and Lighthouse evaluation, optional WAVE, screenshots and retained HTML/raw reports.
- Agentic remediation with five explicit intervention policies, adaptive RAG-ACT retrieval, shared configurable per-run limits, bounded refinement and rollback.
- A researcher-managed model catalogue shared by the web interface and browser extension, with frozen choices and no silent model/provider substitution.
- Iteration traces, activity logs, paired comparisons and recorded usage/charges.
- Portable `.warp` evaluation exchange and composition without unnecessary reevaluation.

Acquisition and ordinary Axe/Lighthouse evaluation do **not** use an LLM. Cloud remediation/categorization and WAVE are optional separately configured services that may incur charges.

## Quick start

Requirements: Git, Docker with Compose, and a browser.

```bash
git clone https://github.com/gverafei/web-accessibility-research-platform.git
cd web-accessibility-research-platform
cp .env.example .env
# Edit .env: set private secrets/passwords before starting.
docker compose up -d --build
```

Open **http://localhost** and create a small evaluation under **New acquisition**. Start without WAVE or cloud calls, inspect the results, then configure a model if you want remediation.

The single `docker-compose.yml` builds web, worker, evaluator and dataset-server from the checked-out source; it does not use prebuilt A11yResearch images from Docker Hub. MySQL and Qdrant use their official images. Read the [installation guide](https://gverafei.github.io/web-accessibility-research-platform/getting-started/installation/) for ports, first-start diagnostics and safe shutdown.

> Local research deployment: the supplied application has no production multi-user authentication boundary. Restrict host/network access and do not expose it directly to the public Internet. Keep `.env`, provider keys and research captures private.

## Services

| Service | Responsibility |
| --- | --- |
| Web · Flask | Interface, reports, configuration and exchange |
| Worker · Python | Persistent acquisition, remediation, category jobs and explicit RAG-ACT maintenance |
| Evaluator · Node/Chromium | Browser capture, Axe, Lighthouse and optional WAVE |
| Dataset server | Internal serving of stored HTML and candidates |
| MySQL | Records, settings, provenance and comparisons |
| Qdrant | Optional local ACT retrieval |

Ollama is optional and configured externally. MySQL/Qdrant use named volumes; mounted `results/`, `data/` and `datasets/` contain other persistent evidence. Back up both records and artifacts. Do not delete volumes to repair a service error.

## Browser extension

Load `browser_extension/` as an unpacked extension in a compatible Chromium browser. The documented prototype targets Chrome/Edge and expects A11yResearch at localhost. It submits the active tab's URL, not its cookies/session/live DOM. See the [extension guide](https://gverafei.github.io/web-accessibility-research-platform/guide/extension/) for controls, permissions and capture scope.

## Development and verification

```bash
python -m pip install -r web/requirements.txt
pybabel compile -d web/app/translations
python -m unittest discover -s web/tests -q
git diff --check
```

Use the [development guide](https://gverafei.github.io/web-accessibility-research-platform/development/) for the Docker test environment, evaluator/extension tests and research-control contracts.

## Documentation source

The full site is authored in `docs/site/`, configured in `mkdocs.yml`, and deployed to GitHub Pages by `.github/workflows/documentation.yml`.

```bash
python -m pip install -r requirements-docs.txt
python docs/tools/check_examples.py
mkdocs build --strict
python docs/tools/check_site.py
mkdocs serve --dev-addr 127.0.0.1:8001
```

Only documentation becomes a Pages artifact; the site does not run A11yResearch or publish the database/captured pages.

## License and citation

[MIT](LICENSE). Cite the repository and the exact release/commit used until a publication/archive citation is available. See [citation and provenance guidance](https://gverafei.github.io/web-accessibility-research-platform/reference/citation/). Third-party website captures and ACT/dependency material retain their own rights and attribution.
