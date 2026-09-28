# Settings reference

The authoritative defaults are in `web/app/settings.py`; deployment bootstrap values also come from `.env.example`, Compose and `config.py`. Persisted settings override recognized defaults. Some effective values can therefore differ from this table on an existing installation.

## Research and provider settings

| Persisted key | Code default | Meaning |
| --- | --- | --- |
| `remediation_min_lighthouse` | `94` | New-run minimum Lighthouse target |
| `remediation_max_axe` | `3` | New-run maximum Axe-instance target |
| `remediation_model_catalog_json` | Empty → bundled catalogue | Researcher-managed cloud choices |
| `ollama_base_url` | Empty | External local service address |
| `ollama_model` | Empty | Explicit installed local model |
| `ollama_capabilities_json` | `[]` | Derived model capabilities, not user-authored settings |
| `openrouter_api_key` | `OPENROUTER_API_KEY` or empty | Cloud credential |
| `openrouter_base_url` | `https://openrouter.ai/api/v1` | Discovery/chat API base |
| `wave_api_key` | `WAVE_API_KEY` or empty | Optional WAVE credential |
| `wave_report_type` | `2` | Detailed WAVE evaluation mode |
| `wave_eval_delay_ms` | `2000` | Configured WAVE delay |
| `wave_cost_per_credit_usd` | `0.04` | Configured accounting reference, not a live price quote |
| `internal_dataset_urls` | Environment value or empty | Optional default URL list |

The research-target form validates Lighthouse within 0–100 and nonnegative Axe counts. The catalogue uses its own validation and save endpoint. Local capabilities are discovered from the model rather than trusted from arbitrary form values.

## Evaluator and display settings

| Key | Code default |
| --- | --- |
| `axe_standard` | `wcag22aa` |
| `axe_include_best_practices` | `false` |
| `show_axe_failed_rules` | `false` |
| `show_axe_needs_review` | `false` |
| `show_axe_densities` | `false` |
| `app_timezone` | `America/Mexico_City` |
| `page_load_timeout_ms` | `60000` |
| `network_idle_timeout_ms` | `15000` |
| `page_settle_delay_ms` | `2000` |
| `dom_stability_window_ms` | `1500` |
| `dom_stability_timeout_ms` | `10000` |
| `enable_lazy_load_scroll` | `true` |
| `scroll_step_px` | `700` |
| `scroll_delay_ms` | `400` |
| `max_scroll_steps` | `30` |

Most timing settings have matching uppercase environment defaults. The example environment can set a different pilot policy, so retain the **effective** configuration and actual load metadata for reproducibility.

Display flags govern report presentation; they are not proof that a previous result was remeasured under newly selected standards.

## Process/deployment environment

| Variable | Role |
| --- | --- |
| `SECRET_KEY` | Flask session signing; change the example/default value |
| `APP_TIMEZONE` | Process/default application time zone |
| `EVALUATOR_URL` | Internal evaluator service, normally `http://evaluator:3000` |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Application database connection |
| `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` | MySQL initialization variables |
| `MAX_DATASET_UPLOAD_BYTES` | HTTP upload limit, default 1,610,612,736 bytes |
| `DATASET_ROOT` | Python artifact/dataset root, default `/datasets` |
| `QDRANT_URL` | Retrieval service, default `http://qdrant:6333` |
| `RAG_COLLECTION` | Retrieval collection, default `wcag_act_examples` |

Changing MySQL initialization variables does not automatically change credentials in an already-initialized volume. Coordinate database user changes through database administration rather than deleting valid research data.

## Pure recipe example

```python
# docs-test: offline
from remediation_recipes import automatic_recipe

settings = {"remediation_min_lighthouse": "95", "remediation_max_axe": "2"}
minimal = automatic_recipe(15, settings=settings)
regeneration = automatic_recipe(75, settings=settings)
assert (minimal["lighthouse"], minimal["axe"]) == (95, 2)
assert (regeneration["lighthouse"], regeneration["axe"]) == (95, 2)
assert minimal["iterations"] == regeneration["iterations"] == 3
assert minimal["cost"] < regeneration["cost"]
```

This verifies that intervention recipes can change continuation budgets while shared targets remain fixed. It does not make model calls or alter the database.

## Secrets and updates

OpenRouter/WAVE keys are sensitive persisted settings. Treat database backups as secret-bearing files. The UI avoids requiring a key to be reentered for every unrelated save; inspect the explicit clear/replace behavior before removing one.

Non-secret controls and the frozen model snapshot provide the configuration needed to reproduce an experiment. Provider credentials stay in the installation's private environment.
