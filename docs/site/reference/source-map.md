# Source map

Shared request indicators and upper-page notifications are implemented in
`web/app/static/js/ui_feedback.js` and mounted by `web/app/templates/base.html`.
Explicit AJAX controls reuse the same busy-state helper; visual rules live in
the canonical `web/app/static/css/theme.css`.

Shared history layouts use `web/app/static/js/history_views.js` and
`web/app/templates/_history_view_toggle.html`; their presentation lives in the
canonical `web/app/static/css/theme.css`. Table and card modes reuse each record
rather than creating independent copies of its state or actions.
`web/app/templates/_history_view_head.html` loads the shared preference before
the list is painted; controls bind after the document is ready.

This map connects documentation topics to their implementation files. Paths are relative to the repository root.

| Area | Primary implementation |
| --- | --- |
| Application/bootstrap | `web/app/main.py`, `web/app/config.py` |
| General settings/targets | `web/app/settings.py`, `web/app/remediation_recipes.py` |
| Catalogue/discovery | `web/app/remediation_model_choices.py`, `web/app/routes/model_catalog.py` |
| Ollama | `web/app/local_llm.py` |
| Evaluation routing/report analysis | `web/app/routes/experiments.py` |
| Job processing and recovery | `web/app/jobs.py`, `web/app/worker.py` |
| Tranco selector/reserves | `web/app/tranco_sampling.py` |
| Local HTML import | `web/app/dataset_storage.py`, `dataset_server/server.py` |
| Managed URL pagination | `web/app/managed_url_catalog.py`, `web/app/static/js/managed_urls.js` |
| Categorization | `web/app/classify_site_categories.py` |
| Experiment portability | `web/app/result_portability.py` |
| Comparison analysis | `web/app/routes/comparisons.py` |
| Remediation submission/report | `web/app/routes/remediation.py` |
| Remediation analytical CSV | `web/app/remediation_csv.py`; read-only download route in `web/app/routes/remediation.py` |
| Native download readiness | `web/app/download_feedback.py`; shared button feedback in `web/app/static/js/ui_feedback.js` |
| Remediation exchange | `web/app/remediation_portability.py`, `web/app/warp_export.py`; import dispatch in `web/app/routes/experiments.py` |
| Main remediation orchestration | `web/app/remediation_jobs.py` |
| State machine and skills | `web/app/remediation_agent_runtime.py`, `web/app/remediation_skill_catalog.py`, `web/app/agent_skills/manifest.json` |
| Typed tool contracts | `web/app/remediation_tool_registry.py` |
| Intervention constraints | `web/app/remediation_approaches.py` |
| Selection/completion/stopping | `web/app/remediation_selection.py`, `web/app/remediation_completion.py`, `web/app/remediation_adaptive.py` |
| Source preservation and replay | `web/app/remediation_content_contract.py` |
| Whole-document prompt and design references | `web/app/vera_prompt.py`, `web/app/vera_regeneration.py`, `web/app/regeneration_references.py` |
| Markdown extraction | `web/app/remediation_extraction.py` |
| ACT retrieval/synchronization and example browser | `web/app/remediation_rag.py`, `web/app/sync_act_rag.py`, `web/app/remediation_rag_supplement.py`, `web/app/rag_corpus.py`, `web/app/rag_sync_jobs.py`, `web/app/rag_examples.py`, `web/app/routes/rag_maintenance.py` |
| Shared navigation and breadcrumbs | `web/app/navigation.py`, `web/app/templates/base.html`, `web/app/templates/_breadcrumbs.html`, `web/app/static/css/theme.css` |
| Database/schema | `web/app/database.py` |
| Extension API/configuration | `web/app/routes/extension_api.py`, `web/app/browser_extension_config.py` |
| Extension client | `browser_extension/manifest.json`, `browser_extension/controls.js`, `browser_extension/sidepanel.js`, `browser_extension/service-worker.js` |
| Evaluator boundary | `evaluator/server.js`, `evaluator/acquisition_quality.js` |
| Axe/browser isolation | `evaluator/run_axe.js`, `evaluator/run_axe_isolated.js`, `evaluator/isolated_process.js` |
| Lighthouse/WAVE | `evaluator/run_lighthouse.js`, `evaluator/lighthouse_score.js`, `evaluator/run_wave.js` |
| Scatter visuals | `web/app/static/js/scatter_visuals.js` |
| Configuration tabs | `web/app/static/js/configuration_tabs.js`, `web/app/static/css/configuration.css` |

Browse the [source repository](https://github.com/gverafei/web-accessibility-research-platform).

## Where to change common behavior

- Fresh cloud defaults: `default_catalog()` in `web/app/remediation_model_choices.py`.
- Shared target defaults and validation: `web/app/settings.py` and `web/app/remediation_recipes.py`.
- Intervention policies: `web/app/remediation_approaches.py`.
- Candidate ranking and rollback: `web/app/remediation_selection.py`.
- Acquisition policy: evaluator modules and runtime settings in `web/app/settings.py`.
- Documentation sidebar: `mkdocs.yml`; page sources: `docs/site`.
