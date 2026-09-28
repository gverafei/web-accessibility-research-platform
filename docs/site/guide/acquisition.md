# URL acquisition and evaluation

The URL workflow visits public HTTP(S) pages, captures evidence and measures accessibility. It does not require or invoke an LLM.

## Create an evaluation

1. Open **New acquisition** and choose URLs.
2. Enter one address per line, up to 100 manually entered URLs per submission.
3. Give the evaluation a recognizable name, up to 160 characters.
4. Decide whether to reuse compatible stored results.
5. Enable WAVE only if needed and configured.
6. Submit and follow the job in **Evaluations**.

The ordinary acquisition form limits an evaluation to 1,000 observations. A research-specific script/protocol can define a different collection, but that does not change the UI limit. For a ranking-based sample, use the [Tranco workflow](tranco.md); for captured files, use [local HTML](local-html.md).

## Fresh versus reused observations

With reuse enabled, WARP looks for a completed compatible record rather than performing an unnecessary new visit. The signature includes evaluation controls such as tool selection, Axe standard and dynamic-page timing. Reused records retain source identifiers and their original evaluation date; their copy does not represent a fresh visit on the composition date.

Disable reuse when your research question requires a current measurement. Check provenance in the report before treating any collection as a single-time snapshot of the web.

## Progress and pause

The worker processes requested URLs and commits evidence as it progresses. You can leave the list/report and return later. **Pause** stops scheduling additional observations at a safe boundary; it does not necessarily abort a browser already acquiring a page. **Resume** continues the remaining work and can apply the recovery behavior recorded for a Tranco evaluation.

Recorded processing seconds are not necessarily the elapsed wall-clock duration. Reused results incur no new browser evaluation in that copy. Interruptions and retries must be interpreted through their own records, not reconstructed from an assumed average.

## What is retained

Successful results can include rendered source HTML, response HTML when available, a screenshot, raw Axe/Lighthouse reports, optional WAVE output, page features and acquisition metadata. Completeness depends on the actual tool response and the acquisition type. Confirm the artifacts rather than assuming a completed counter guarantees every file is present.

An error, challenge page or incomplete tool response must not become a successful zero-issue observation. WARP's quality/recovery handling is described in [Evaluation pipeline](../technical/evaluation.md) and [Jobs and recovery](../technical/jobs.md).

## Practical pilot

Before launching hundreds of pages, evaluate a small set covering the page types you expect. Inspect lazy-loaded content, screenshot completeness, evidence files and per-page duration. Adjust the acquisition settings if warranted, record the changes, and then keep the policy fixed for the main cohort.
