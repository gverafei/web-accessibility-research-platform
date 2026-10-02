# Installation

A11yResearch runs as six cooperating Docker services. Its single `docker-compose.yml` builds the application services from the repository so the application, extension and documentation correspond to the same source revision.

## Requirements

- Git and Docker with the Compose plugin (`docker compose`).
- A modern browser for the web application.
- Internet access for live-page acquisition and the initial image/dependency downloads.
- Disk space for captured HTML, raw reports and screenshots. Storage grows with the number and complexity of acquired pages.

There is no measured universal RAM or CPU minimum. Begin with a small evaluation, observe browser memory and disk usage, and increase the cohort only after the pilot succeeds. Ollama is optional and runs outside this Compose stack.

## Clone and configure

```bash
git clone https://github.com/gverafei/web-accessibility-research-platform.git
cd web-accessibility-research-platform
cp .env.example .env
```

Edit `.env` before starting. Set a private `SECRET_KEY`, database passwords and an appropriate time zone. Keep the database name/user consistent with the supplied Compose configuration. Do not commit `.env` or a provider key.

For a first Axe/Lighthouse experiment, leave `OPENROUTER_API_KEY` and `WAVE_API_KEY` empty. Add them only when you want cloud remediation/categorization or WAVE, respectively.

## Build and start

```bash
docker compose up -d --build
docker compose ps
```

Open [http://localhost](http://localhost). MySQL may take longer than the other services to initialize on the first start. If the page is temporarily unavailable, inspect the logs rather than repeatedly rebuilding:

```bash
docker compose logs --tail=100 web db worker
```

The web service compiles the English/Spanish translation catalogues from the checked-out source before serving requests. Compiled catalogues are generated locally, not committed to Git.

Web and worker build from `web/Dockerfile`, evaluator from `evaluator/Dockerfile`, and dataset-server from `dataset_server/Dockerfile`. No prebuilt A11yResearch images are downloaded from Docker Hub. MySQL and Qdrant still use their official images; building the application also downloads base images and dependencies when they are not already cached.

To build without starting or restarting any service:

```bash
docker compose build
```

## Ports and services

| Service | Internal address | Published host address |
| --- | --- | --- |
| Web application | `web:5000` | `http://localhost:80` |
| Worker | No HTTP listener | None |
| Evaluator | `evaluator:3000` | `http://localhost:3000` |
| Dataset server | `dataset-server:8080` | None |
| MySQL | `db:3306` | `localhost:3307` |
| Qdrant | `qdrant:6333` | None |

Service names resolve inside the Docker network; they are not fixed IP addresses. See [architecture](../technical/architecture.md) for mounts and network boundaries.

## Confirm the installation

1. Open **Configuration → General** and inspect the evaluator settings.
2. Create a two-page acquisition without WAVE or an LLM.
3. Confirm the evaluation progresses and opens a report with screenshots, Axe counts and Lighthouse scores.
4. Confirm **Manage URLs** lists the completed acquisitions.

A read-only evaluator health check:

```bash
curl --fail http://localhost:3000/health
```

## Stop and restart safely

```bash
docker compose stop
docker compose start
```

Pause a running evaluation through the UI before maintenance when practical. Do not run `down -v`: it deletes the named database/vector volumes. A database volume alone is not a complete backup; see [storage and backup](../technical/storage.md).

!!! warning "Local research deployment"
    The application does not provide a production multi-user authentication boundary. The supplied host ports are not restricted to loopback by Compose. Use a firewall or loopback port bindings and do not expose this installation directly to the public Internet.
