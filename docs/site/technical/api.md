# HTTP interfaces and automation

A11yResearch's Flask routes support its local UI and extension. They are not a versioned, authenticated public SaaS API. Use the documented inputs against the source revision you pinned and verify the response status before continuing.

!!! warning "Live operations"
    Acquisition examples visit websites and write evidence. Remediation and cloud categorization examples can incur provider charges. The snippets below are documentation, not commands that the documentation build executes.

## Route reference

The full URLs below use the supplied web mapping (`localhost:80`). Replace that base address with your deployment hostname or port when needed. The evaluator uses a separate address, `http://localhost:3000/health`, described in [Evaluation pipeline](evaluation.md#interface).

Route handlers are grouped in `web/app/routes/experiments.py` (acquisition, reports, URL management and configuration), `web/app/routes/remediation.py` (remediation), `web/app/routes/model_catalog.py` (model catalogue) and `web/app/routes/extension_api.py` (browser extension).

| Method | Full host URL | Contract |
| --- | --- | --- |
| GET | `http://localhost/evaluations` or `http://localhost/experiments` | Evaluation list, HTML |
| POST | `http://localhost/run` | Queue acquisition from form/multipart data; redirects to the UI |
| GET | `http://localhost/experiments/<id>` | Prepared evaluation report, HTML |
| GET | `http://localhost/experiments/<id>/loading` | Report loading/transition view |
| POST | `http://localhost/experiments/<id>/pause` | Request pause |
| POST | `http://localhost/experiments/<id>/resume` | Resume allowed pending work |
| GET | `http://localhost/experiments/<id>/csv` | Measurements table download |
| GET | `http://localhost/experiments/<id>/raw/<result_id>/<type>` | Stored artifact attachment; type is `axe`, `lighthouse`, `wave`, `semantic` (JSON), `response` or `rendered` (HTML). Result must belong to the experiment and file must be under `/results/raw`. No acquisition or evaluation |
| GET | `http://localhost/experiments/<id>/json` | `.warp` export (ZIP, not a bare JSON response) |
| GET | `http://localhost/experiments/<id>/tranco-sample.csv` | Sampling manifest where available |
| POST | `http://localhost/experiments/<id>/tranco-fill-missing` | Fill curated vacancies from stored same-stratum reserves |
| POST | `http://localhost/experiments/<id>/tranco-retry-failed` | Retry eligible failures |
| POST | `http://localhost/experiments/<id>/tranco-replace-failed` | Reserve replacement for eligible failures |
| GET | `http://localhost/urls/manage/data` | Bounded catalogue page, JSON with rendered rows |
| POST | `http://localhost/urls/auto-categorize` | Start/check persisted category job, JSON |
| GET | `http://localhost/urls/category-models` | Configured local model and cloud default; model choice IDs |
| GET | `http://localhost/urls/auto-categorize/status` | Persisted category status |
| POST | `http://localhost/urls/auto-categorize/stop` | Stop at a safe batch boundary |
| GET/POST | `http://localhost/configuration/models` | Read/save catalogue JSON |
| GET | `http://localhost/configuration/models/discover` | Explicit OpenRouter metadata discovery |
| GET | `http://localhost/rag-act` | RAG-ACT workspace: maintenance controls and read-only saved-example browser |
| GET | `http://localhost/rag-act/status` | Read corpus counts, recorded date, maintenance progress and active-remediation count; does not synchronize |
| POST | `http://localhost/rag-act/synchronize` | Queue explicit maintenance: JSON `mode` is `initialize` or `update`; updates require boolean `confirmed: true`. HTTP 202 queued, 409 conflicting/active remediation, 503 unavailable service/storage |
| GET/POST | `http://localhost/remediation/new` | Form / queue one source remediation |
| GET | `http://localhost/remediation/<id>` | Run report with evidence |
| GET | `http://localhost/remediation/<id>/export` | Terminal run `.warp` with original/candidates/history |
| GET/POST | `http://localhost/remediation/export` | GET redirects to Remediation runs; POST exports a terminal batch using repeated form field `run_ids` |
| GET | `http://localhost/api/browser-extension/configuration` | Extension model/policy catalogue |
| POST | `http://localhost/api/browser-extension/requests` | Submit URL and frozen research controls |
| GET | `http://localhost/api/browser-extension/requests/<id>` | Resolve/update persistent request progress |
| GET | `http://localhost/api/browser-extension/requests/latest?url=...` | Resolve latest request for a URL |
| GET | `http://localhost/api/browser-extension/requests/<id>/candidate` | Candidate HTML when available |

The extension progress handlers connect a completed acquisition with its remediation run and return the request's current progress. Their implementation is in `web/app/routes/extension_api.py`.

Extension submission snapshots Configuration's effective targets and resource
limits before acquisition. Delayed completion uses that snapshot rather than
later settings. Limits are per run; stored-result reuse preserves the original
run's limits and does not trigger a new execution just because budgets changed.

## Queue a URL evaluation

```bash
curl --fail --dump-header - --output /dev/null \
  --data-urlencode 'title=Two-page acquisition pilot' \
  --data-urlencode 'source_type=url' \
  --data-urlencode $'urls=https://example.org/\nhttps://www.w3.org/' \
  http://localhost/run
```

This Bash/Zsh example expects a redirect, not a JSON job ID. The `Location` header identifies the resulting UI destination. Add `reuse_cached_results=on` only if compatible reuse is intended; add `include_wave=on` only with a configured WAVE key and authorization for its charges. Inspect the UI if validation redirected back to the form.

For a large collection, put one URL per line in a text file and submit that field from the file:

```bash
curl --fail --dump-header - --output /dev/null \
  --data-urlencode 'title=Research collection' \
  --data-urlencode 'source_type=url' \
  --data-urlencode 'urls@urls.txt' \
  http://localhost/run
```

There is no fixed URL-count cap. The request byte budget and installation resources still apply; see [collection planning](../guide/acquisition.md#collection-size-and-resource-planning).

## Query the catalogue

```bash
curl --fail --get \
  --data-urlencode 'q=Education' \
  --data-urlencode 'page=1' \
  --data-urlencode 'size=5' \
  --data-urlencode 'sort=date' \
  --data-urlencode 'direction=desc' \
  http://localhost/urls/manage/data
```

Sizes are 5/10/25/50/100. Sort keys are `url`, `name`, `axe`, `lighthouse`, `category`, `evaluation` and `date`. Invalid values fall back to bounded defaults; filtering is parameterized in SQL.

## Scope a paid category job

```bash
curl --fail --header 'Content-Type: application/json' \
  --data '{"model":"openai/gpt-6-luna","experiment_id":42}' \
  http://localhost/urls/auto-categorize
curl --fail http://localhost/urls/auto-categorize/status
```

First inspect `GET /urls/category-models` and use an enabled choice's exact `id`
as `model`. The example assumes GPT-6 Luna is the configured cloud default;
otherwise replace that ID with the returned default or the configured
`ollama/<model-name>` choice. A cloud choice may include a reasoning suffix in
its ID. New jobs freeze the model/server/reasoning configuration, without API
keys. Legacy `local` means the configured Ollama model, and `luna` only means
GPT-6 Luna when that exact choice is available; neither alias permits fallback.
A specified evaluation must be completed. Omit `experiment_id` only if global
catalogue categorization is intended. An active job is returned with its
persistent status.

The existing Import handler also recognizes `remediation.json` (`warp-remediations`
v1) in a `.warp` upload. It validates every binary hash before creating new
records; terminal imports never submit generation or evaluation jobs. See
[exchange](../guide/exchange.md#export-and-import-remediations) for limits and provenance.

## Submit one explicit remediation

`GET /remediation/<run_id>/csv` downloads `remediation-<run_id>.csv` as UTF-8.
It reads saved run/source/iteration records only, with an original row followed
by iteration rows; missing values stay blank and the recorded retained link is
identified separately from iteration decisions. It returns 404 for a missing
run or source and does not submit jobs or modify evidence. See
[remediation exports](../guide/remediation.md) for accounting and RAG field meanings.

```bash
curl --fail --dump-header - --output /dev/null \
  --data-urlencode 'source_result_id=42' \
  --data-urlencode 'selected_model=openai/gpt-6-luna' \
  --data-urlencode 'preservation_level=0' \
  --data-urlencode 'execution_mode=iterative' \
  --data-urlencode 'act_grounding_configured=1' \
  --data-urlencode 'act_grounding=off' \
  http://localhost/remediation/new
```

The model value is a configured **choice ID**. `preservation_level` is zero-based (0–4), while the UI displays levels 1–5. Choose a completed source result with a readable snapshot. Targets come from General settings and are saved with the submitted run.

## Extension request

```bash
curl --fail --header 'Content-Type: application/json' \
  --data '{"url":"https://example.org/","selected_model":"openai/gpt-6-luna","preservation_level":0,"use_rag":false}' \
  http://localhost/api/browser-extension/requests
```

New requests return HTTP 202 with `id`, initial status and `reused: false`. Compatible stored or in-progress requests return HTTP 200 with `reused: true`; no new run is created. Reuse is the default and matches the normalized URL, actual model/reasoning and intervention slider. RAG, targets, catalogue presentation and a newer source acquisition do not invalidate a retained result. Recovering a backend run creates only a delivery request linked to that run. Progress includes the recovered run's `configuration`, not the controls submitted to find it. Add the JSON boolean `"force_rerun": true` to request a fresh acquisition (without evaluation-cache reuse) and a new remediation. An omitted `preservation_level` defaults to 0 (Minimal patches).

Use that ID to poll progress until processing finishes. Terminal responses include `report_url` and `measurements`: `original` and `final` each contain `axe` and `lighthouse`; `targets` contains their frozen thresholds; `iteration_id` identifies the served retained candidate. Missing measurements are JSON `null`. Linked acquisition records provide source provenance and the original capture date. Implementation: `web/app/routes/extension_api.py` and `web/app/browser_extension_results.py`.

## Inspect saved RAG-ACT examples

`GET /rag-act` renders the workspace with a read-only local corpus browser.
Query parameters: `q` (rule/title/IDs/requirements), `source` (`official` or
`complementary`), `outcome` (`passed` or `failed`), `size` (5/10/20/25/50/100/250/500)
and `page`. Counts describe saved examples, not the entire upstream catalogue.
`GET /rag-act/examples/<UUID>` shows stored HTML as escaped text
and recorded provenance, without executing scripts or loading example resources.
Links carry the active `collection` to detect snapshot changes (HTTP 409); the
route cannot browse an arbitrary Qdrant collection. Unavailable inspection is
HTTP 503; absent examples are HTTP 404. Neither GET requests maintenance or LLMs.

## Catalogue JSON

Read `http://localhost/configuration/models` first. POST a JSON object with a `choices` array validated by `validate_catalog()` in `web/app/remediation_model_choices.py`. Preserve required IDs, explicit provider/model identifiers, enabled/default fields, tier, hex color and capability/reasoning metadata. Saving a catalogue is a configuration write and does not retroactively update runs.

Prefer the catalogue UI for normal administration. [Models and reasoning](../guide/models.md) explains manual future identifiers and how to avoid unsupported capability flags.
