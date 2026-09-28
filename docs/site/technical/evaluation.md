# Evaluation pipeline

The evaluator is a Node/Express service backed by browser/tool processes. Its typed response is consumed by the Python worker. The evaluator does not invoke an LLM to invent missing findings.

## Interface

`GET /health` returns service/tool health metadata. `POST /evaluate` accepts an experiment ID, a nonempty URL array and explicit tool/runtime controls. The internal HTTP interface is not an authenticated public cloud API.

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

Calling this endpoint visits pages and writes artifacts. For normal research work, submit through WARP so the persistent experiment record, progress and provenance are also managed.

## Execution

For each requested URL, the service runs isolated Axe acquisition and Lighthouse work, plus WAVE if requested. Tool promises are collected so failures retain their individual error context. The outer response can be completed while some items failed; consumers must inspect each item.

The Axe acquisition path provides rendered HTML, optional response-source HTML, screenshot and page/load features. It gathers the required rule evidence and variants so display choices can be separated from the underlying capture.

Lighthouse uses its own controlled process/browser path. Its accessibility score is validated before use. WAVE is an independent remote API path for public URLs and has its own delay/usage metadata.

## Quality checks

`acquisition_quality.js` validates the requested quality policy and evaluates available acquisition evidence. The Python worker refuses to turn an item with failed status into a valid stored observation. Remediation additionally requires both Axe and Lighthouse measurements before ranking a candidate.

A challenge response, unusable capture or incomplete evaluator response is a technical problem, not evidence that the page has no accessibility barriers. Keep original tool errors when diagnosing it.

## Response contents

A successful page item can include its URL/status, execution time, screenshot path/mode, acquisition metadata, rendered/response snapshot paths, page features, Axe summaries/raw path, Lighthouse score/raw path and optional WAVE result/status/charges.

Environment metadata records actual Node, browser, Axe and Lighthouse versions plus relevant policy/image context. Dependency files describe requested versions; stored environment metadata describes the execution that actually produced the observation.

## Artifacts

The service writes raw reports and captured sources under the experiment's artifact directory. Artifact paths are internal references. Web download handlers enforce the applicable result/experiment association and allowed roots before serving them.

## Resource isolation

Browser/tool execution is separated into helper processes to contain timeout/crash effects. Docker remains a local research environment, not a guarantee that arbitrary hostile HTML is harmless. Restrict the reachable network and protect credentials; see [Security](security.md).

## Tests

The evaluator package includes policy, score and process tests:

```bash
docker compose exec evaluator npm test
```

Use a bounded live-page pilot separately. Unit tests do not establish that every current website is reachable or that independent tools will observe the same dynamic state.
