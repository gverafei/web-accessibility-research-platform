# Troubleshooting

The affected record, its error details and the corresponding service logs are the starting points for diagnosis.

## Evaluation remains queued

Check that `worker` is running and inspect its recent logs. The current scheduler prioritizes remediation before evaluation, so another active run can delay acquisition. Confirm a single worker is attached to the correct database and that the evaluator is reachable.

```bash
docker compose ps
docker compose logs --tail=100 worker evaluator db
```

An unavailable evaluator leaves acquisition queued for recovery. Restoring that service allows processing to continue with the same candidates.

## Progress appears stalled

A complex page can spend significant time within bounded browser/tool work. Compare committed observations or progress evidence across a meaningful interval. Pause/resume only through the supported UI and inspect errors before submitting a second experiment.

## Ollama fails or the dropdown has no local choice

Configure both base URL and installed model. Refresh/test from the Local LLM panel. Confirm Docker can reach Ollama: container-local `localhost` is usually not the host service. An unavailable local model is not replaced automatically by a cloud model.

Context-capacity errors identify a page that exceeds the selected model's input capacity. A model with a larger context window or a localized intervention may suit that page.

## Cloud model returns 401/403 or is unavailable

Check the configured OpenRouter credential, exact model ID and account access. The run log identifies the provider request and its error details. Credentials can be updated in the installation's private environment configuration.

## Missing thumbnail or incomplete capture

Inspect screenshot/source/raw-report paths and acquisition metadata. Check that the artifact exists and the result belongs to the intended evaluation. A challenge, network error or incomplete page is not a zero-issue result.

For dynamic content, run a small pilot and inspect scroll/stability behavior. A required login/click is outside a generic URL capture. Replace only technically invalid/out-of-scope records under the declared same-stratum reserve policy.

## Categorization stops or mislabels pages

Check the persisted job and selected classifier before starting another. The classifier uses title/URL, not the full page, so some labels need review. Unknown categories, unexpected IDs and malformed output are rejected; validated assignments already committed remain available.

## Candidate retained with warnings

Read the target values, iteration decisions and activity events. A warning can indicate that processing stopped at a budget or plateau limit while retaining a measured candidate below the configured target.

## Import or local dataset fails

Use `.warp` for evaluation exchange and the local HTML workflow for captured files. Import error details identify payload-version, URL, path, size or resource-reference problems.

## Documentation deployment fails

Inspect the **Documentation** Actions run, confirm Pages Source is **GitHub Actions**, and check the `github-pages` environment's branch permission. Run `mkdocs build --strict` and the two documentation checkers locally. A missing public page before the first deployment is not an application problem.
