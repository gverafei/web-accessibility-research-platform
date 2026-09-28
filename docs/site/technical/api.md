# HTTP interfaces and automation

WARP's Flask routes support its local UI and extension. They are not a versioned, authenticated public SaaS API. Use the documented inputs against the source revision you pinned and verify the response status before continuing.

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
| GET | `http://localhost/experiments/<id>/json` | `.warp` export (ZIP, not a bare JSON response) |
| GET | `http://localhost/experiments/<id>/tranco-sample.csv` | Sampling manifest where available |
| POST | `http://localhost/experiments/<id>/tranco-fill-missing` | Fill curated vacancies from stored same-stratum reserves |
| POST | `http://localhost/experiments/<id>/tranco-retry-failed` | Retry eligible failures |
| POST | `http://localhost/experiments/<id>/tranco-replace-failed` | Reserve replacement for eligible failures |
| GET | `http://localhost/urls/manage/data` | Bounded catalogue page, JSON with rendered rows |
| POST | `http://localhost/urls/auto-categorize` | Start/check persisted category job, JSON |
| GET | `http://localhost/urls/auto-categorize/status` | Persisted category status |
| POST | `http://localhost/urls/auto-categorize/stop` | Stop at a safe batch boundary |
| GET/POST | `http://localhost/configuration/models` | Read/save catalogue JSON |
| GET | `http://localhost/configuration/models/discover` | Explicit OpenRouter metadata discovery |
| GET/POST | `http://localhost/remediation/new` | Form / queue one source remediation |
| GET | `http://localhost/remediation/<id>` | Run report with evidence |
| GET | `http://localhost/api/browser-extension/configuration` | Extension model/policy catalogue |
| POST | `http://localhost/api/browser-extension/requests` | Submit URL and frozen research controls |
| GET | `http://localhost/api/browser-extension/requests/<id>` | Resolve/update persistent request progress |
| GET | `http://localhost/api/browser-extension/requests/latest?url=...` | Resolve latest request for a URL |
| GET | `http://localhost/api/browser-extension/requests/<id>/candidate` | Candidate HTML when available |

The extension progress handlers connect a completed acquisition with its remediation run and return the request's current progress. Their implementation is in `web/app/routes/extension_api.py`.

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
  --data '{"model":"luna","experiment_id":42}' \
  http://localhost/urls/auto-categorize
curl --fail http://localhost/urls/auto-categorize/status
```

`model` accepts `local` or `luna`. A specified evaluation must be completed. Omit `experiment_id` only if global catalogue categorization is intended. An active job is returned with its persistent status.

## Submit one explicit remediation

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

Success returns HTTP 202 with `id` and initial status. Use that ID to poll progress until processing finishes. Linked acquisition records provide the source provenance and original capture date.

## Catalogue JSON

Read `http://localhost/configuration/models` first. POST a JSON object with a `choices` array validated by `validate_catalog()` in `web/app/remediation_model_choices.py`. Preserve required IDs, explicit provider/model identifiers, enabled/default fields, tier, hex color and capability/reasoning metadata. Saving a catalogue is a configuration write and does not retroactively update runs.

Prefer the catalogue UI for normal administration. [Models and reasoning](../guide/models.md) explains manual future identifiers and how to avoid unsupported capability flags.
