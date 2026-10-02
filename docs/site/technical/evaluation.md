# Evaluation pipeline

The evaluator is a Node/Express service that runs browser-based accessibility tools. It returns their measurements, captured evidence and execution metadata to the Python worker.

## Interface

Main research scores and remediation thresholds use WCAG issue instances with Best Practices excluded. The evaluator retains WCAG findings, Best Practices and their combined count separately. In the raw evaluator response, `axe.violations` is the combined count and `axe.wcag_violations` is the WCAG count. The application uses the latter for charts, tables, comparisons and targets. The report switch only shows an additional Best Practices column; it never changes the main metric.

CSV exports identify the main WCAG count as `axe_issue_instances`, with separate `axe_best_practice_issues` and `axe_combined_issue_instances` columns. Portable `.warp` files preserve the underlying separated fields and original raw evidence. Historical acceptance decisions remain recorded as originally made; corrected display counts do not retroactively change run status.

The evaluator endpoints are implemented in `evaluator/server.js`. With the supplied Compose configuration:

| Method | Full URL from the host | Purpose |
| --- | --- | --- |
| GET | `http://localhost:3000/health` | Service and tool health metadata |
| POST | `http://localhost:3000/evaluate` | Evaluate an experiment ID, nonempty URL array and explicit tool/runtime controls |

The application itself is at `http://localhost/` (port 80), so `http://localhost/health` addresses a different service. Inside the Docker network, the worker reaches these endpoints at `http://evaluator:3000/health` and `http://evaluator:3000/evaluate`. Different host bindings or a reverse proxy change the host URLs; service DNS names continue to use internal ports.

For a host-side health check:

```bash
curl --fail http://localhost:3000/health
```

The evaluator HTTP interface is intended for the local deployment. Normal acquisition submission uses the web application and its persistent queue.

```json
{
  "experiment_id": 42,
  "urls": ["https://example.org/"],
  "include_wave": false,
  "axe_standard": "wcag22aa",
  "axe_include_best_practices": false,
  "runtime_config": {},
  "quality_policy": {}
}
```

Calling this endpoint visits pages and writes artifacts. For normal research work, submit through A11yResearch so the persistent experiment record, progress and provenance are also managed.

## Execution

For each requested URL, the service runs isolated Axe acquisition and Lighthouse work, plus WAVE if requested. Each tool result includes its status and error details. A batch response can finish with a mixture of successful and failed page items; the item status identifies which measurements are available.

The Axe acquisition path provides rendered HTML, optional response-source HTML, screenshot and page/load features. It gathers the required rule evidence and variants so display choices can be separated from the underlying capture.

Lighthouse uses its own controlled process/browser path. Its accessibility score is validated before use. WAVE is an independent remote API path for public URLs and has its own delay/usage metadata.

## Quality checks

`evaluator/acquisition_quality.js` validates the requested quality policy and checks the acquisition evidence. The worker stores unsuccessful items with failed status and error details, separately from valid observations. Candidate ranking in remediation uses both Axe and Lighthouse measurements.

Challenge responses, unusable captures and incomplete tool responses appear as acquisition problems, with the original error available for diagnosis.

## Response contents

A successful page item can include its URL/status, execution time, screenshot path/mode, acquisition metadata, rendered/response snapshot paths, page features, Axe summaries/raw path, Lighthouse score/raw path and optional WAVE result/status/charges.

Environment metadata records actual Node, browser, Axe and Lighthouse versions plus relevant policy/image context. Dependency files describe requested versions; stored environment metadata describes the execution that actually produced the observation.

## Artifacts

The service writes raw reports and captured sources under the experiment's artifact directory. Artifact paths are internal references. Web download handlers enforce the applicable result/experiment association and allowed roots before serving them.

## Resource isolation

Browser/tool execution uses helper processes to contain timeout and crash effects. Network restrictions and credential isolation are configured at deployment level; see [Security](security.md).

## Tests

The evaluator package includes policy, score and process tests:

```bash
docker compose exec evaluator npm test
```

The tests cover tool responses, acquisition policies and process handling with controlled inputs. A live-page pilot can additionally check rendering and connectivity for the sites in a planned collection.
