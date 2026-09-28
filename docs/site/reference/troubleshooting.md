# Troubleshooting

Start with the affected record and service. Do not duplicate paid work, clear the database or rebuild the whole stack before identifying the failing boundary.

## Evaluation remains queued

Check that `worker` is running and inspect its recent logs. The current scheduler prioritizes remediation before evaluation, so another active run can delay acquisition. Confirm a single worker is attached to the correct database and that the evaluator is reachable.

```bash
docker compose -f docker-compose-dev.yml ps
docker compose -f docker-compose-dev.yml logs --tail=100 worker evaluator db
```

If the evaluator is restarting/unavailable, repair that service first. Do not replace a valid candidate because a service outage prevented measurement.

## Progress appears stalled

A complex page can spend significant time within bounded browser/tool work. Compare committed observations or progress evidence across a meaningful interval. Pause/resume only through the supported UI and inspect errors before submitting a second experiment.

## Ollama fails or the dropdown has no local choice

Configure both base URL and installed model. Refresh/test from the Local LLM panel. Confirm Docker can reach Ollama: container-local `localhost` is usually not the host service. An unavailable local model is not replaced automatically by a cloud model.

For context errors, use a suitable explicit local model/context setting or a localized approach on that page. WARP should not hide the problem by truncating a complete source.

## Cloud model returns 401/403 or is unavailable

Confirm the configured OpenRouter credential and exact model ID. Do not paste keys into an issue or this site's source. Catalogue discovery/metadata does not guarantee an account has access to every model.

A 401 in a coding/chat application is not automatically a WARP provider error. Identify the service/URL associated with the failing call and compare it with WARP's run log before changing platform credentials.

## Missing thumbnail or incomplete capture

Inspect screenshot/source/raw-report paths and acquisition metadata. Check that the artifact exists and the result belongs to the intended evaluation. A challenge, network error or incomplete page is not a zero-issue result.

For dynamic content, run a small pilot and inspect scroll/stability behavior. A required login/click is outside a generic URL capture. Replace only technically invalid/out-of-scope records under the declared same-stratum reserve policy.

## Categorization stops or mislabels pages

Check the persisted job and selected classifier before starting another. The classifier uses title/URL, not the full page, so some labels need review. Unknown categories, unexpected IDs and malformed output are rejected; validated assignments already committed remain available.

## Candidate retained with warnings

Read target values, iteration decisions and activity events. The run may have produced a valid measured candidate without meeting targets before its limits or plateau stop. That is not equivalent to no output, and deleting the warning does not improve the experiment.

## Import or local dataset fails

Distinguish `.warp` experiment exchange from HTML dataset ingestion. Check payload version, duplicate URLs, ZIP paths, size limits and relative resource references. Do not disable path/size validation to accept an untrusted archive.

## Documentation deployment fails

Inspect the **Documentation** Actions run, confirm Pages Source is **GitHub Actions**, and check the `github-pages` environment's branch permission. Run `mkdocs build --strict` and the two documentation checkers locally. A missing public page before the first deployment is not an application problem.
