# HTTP interfaces and automation

WARP's Flask routes support its local UI and extension. They are not a versioned, authenticated public SaaS API. Use the documented inputs against the source revision you pinned and verify the response status before continuing.

!!! warning "Live operations"
    Acquisition examples visit websites and write evidence. Remediation and cloud categorization examples can incur provider charges. The snippets below are documentation, not commands that the documentation build executes.

## Route reference

| Method | Path | Contract |
| --- | --- | --- |
| GET | `/evaluations` or `/experiments` | Evaluation list, HTML |
| POST | `/run` | Queue acquisition from form/multipart data; redirects to the UI |
| GET | `/experiments/<id>` | Prepared evaluation report, HTML |
| GET | `/experiments/<id>/loading` | Report loading/transition view |
| POST | `/experiments/<id>/pause` | Request pause |
| POST | `/experiments/<id>/resume` | Resume allowed pending work |
| GET | `/experiments/<id>/csv` | Measurements table download |
| GET | `/experiments/<id>/json` | `.warp` export (ZIP, not a bare JSON response) |
| GET | `/experiments/<id>/tranco-sample.csv` | Sampling manifest where available |
| POST | `/experiments/<id>/tranco-fill-missing` | Fill curated vacancies from stored same-stratum reserves |
| POST | `/experiments/<id>/tranco-retry-failed` | Retry eligible failures |
| POST | `/experiments/<id>/tranco-replace-failed` | Reserve replacement for eligible failures |
| GET | `/urls/manage/data` | Bounded catalogue page, JSON with rendered rows |
| POST | `/urls/auto-categorize` | Start/check persisted category job, JSON |
| GET | `/urls/auto-categorize/status` | Persisted category status |
| POST | `/urls/auto-categorize/stop` | Stop at a safe batch boundary |
| GET/POST | `/configuration/models` | Read/save catalogue JSON |
| GET | `/configuration/models/discover` | Explicit OpenRouter metadata discovery |
| GET/POST | `/remediation/new` | Form / queue one source remediation |
| GET | `/remediation/<id>` | Run report with evidence |
| GET | `/api/browser-extension/configuration` | Extension model/policy catalogue |
| POST | `/api/browser-extension/requests` | Submit URL and frozen research controls |
| GET | `/api/browser-extension/requests/<id>` | Resolve/update persistent request progress |
| GET | `/api/browser-extension/requests/latest?url=...` | Resolve latest request for a URL |
| GET | `/api/browser-extension/requests/<id>/candidate` | Candidate HTML when available |

The extension progress GET handlers can resolve a completed acquisition into its linked remediation run. They are workflow-resolving reads, not guaranteed side-effect-free health probes.

## Queue a URL evaluation

```bash
curl --fail --dump-header - --output /dev/null \
  --data-urlencode 'title=Two-page acquisition pilot' \
  --data-urlencode 'source_type=url' \
  --data-urlencode $'urls=https://example.org/\nhttps://www.w3.org/' \
  http://localhost/run
```

This Bash/Zsh example expects a redirect, not a JSON job ID. The `Location` header identifies the resulting UI destination. Add `reuse_cached_results=on` only if compatible reuse is intended; add `include_wave=on` only with a configured WAVE key and authorization for its charges. Inspect the UI if validation redirected back to the form.

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

`model` accepts `local` or `luna`. A specified evaluation must be completed. Omit `experiment_id` only if global catalogue categorization is intended. The singleton job is returned if already active; do not submit duplicate work through an alternate path.

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

The model value is a configured **choice ID**. `preservation_level` is zero-based (0–4), while the UI displays levels 1–5. Choose a completed source result with a readable snapshot. Targets come from General settings; this minimal example does not enable legacy expert overrides.

## Extension request

```bash
curl --fail --header 'Content-Type: application/json' \
  --data '{"url":"https://example.org/","selected_model":"openai/gpt-6-luna","preservation_level":0,"use_rag":false}' \
  http://localhost/api/browser-extension/requests
```

Success returns HTTP 202 with `id` and initial status. Poll the specific request ID. Do not POST again simply because acquisition is slow. The response `reused` flag is not a complete acquisition-provenance report; inspect the linked records for reused frozen evidence.

## Catalogue JSON

Read `/configuration/models` first. POST a JSON object with a `choices` array validated by `validate_catalog()`. Preserve required IDs, explicit provider/model identifiers, enabled/default fields, tier, hex color and capability/reasoning metadata. Saving a catalogue is a configuration write and does not retroactively update runs.

Prefer the catalogue UI for normal administration. [Models and reasoning](../guide/models.md) explains manual future identifiers and how to avoid unsupported capability flags.
