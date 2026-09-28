# Source map

This map connects the public documentation to the current implementation. Paths are relative to the repository root. The documentation checker verifies that these source files exist; behavior still requires code/tests and a relevant pilot.

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
| Main remediation orchestration | `web/app/remediation_jobs.py` |
| State machine and skills | `web/app/remediation_agent_runtime.py`, `web/app/remediation_skill_catalog.py`, `web/app/agent_skills/manifest.json` |
| Typed tool contracts | `web/app/remediation_tool_registry.py` |
| Intervention constraints | `web/app/remediation_approaches.py` |
| Selection/completion/stopping | `web/app/remediation_selection.py`, `web/app/remediation_completion.py`, `web/app/remediation_adaptive.py` |
| Source preservation and replay | `web/app/remediation_content_contract.py` |
| Regeneration/design references | `web/app/vera_regeneration.py`, `web/app/regeneration_references.py` |
| Markdown extraction | `web/app/remediation_extraction.py` |
| ACT retrieval/synchronization | `web/app/remediation_rag.py`, `web/app/sync_act_rag.py`, `web/app/remediation_rag_supplement.py` |
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

- Change fresh cloud defaults in `default_catalog()`, not in duplicated extension markup.
- Change shared target defaults/validation in settings and recipes, then verify freezing in both web and extension requests.
- Change intervention constraints in `remediation_approaches.py`, not just a slider label.
- Change ranking/rollback in `remediation_selection.py` and test retention of the best evaluated candidate.
- Change acquisition policy in the evaluator/runtime settings and preserve actual environment evidence.
- Change the published sidebar in `mkdocs.yml`; page sources are in `docs/site`.
