# URL acquisition and evaluation

The URL workflow visits public HTTP(S) pages, captures evidence and measures accessibility. It does not require or invoke an LLM.

## Create an evaluation

1. Open **New acquisition** and choose URLs.
2. Enter one address per line; choose the collection size required by your study.
3. Give the evaluation a recognizable name, up to 160 characters.
4. Decide whether to reuse compatible stored results.
5. Enable WAVE only if needed and configured.
6. Submit and follow the job in **Evaluations**.

There is no fixed observation-count cap in the acquisition form or queueing handler, for either URLs, Tranco samples or local HTML. For a ranking-based sample, use the [Tranco workflow](tranco.md); for captured files, use [local HTML](local-html.md).

## Collection size and resource planning

A researcher can request thousands of pages or a million-page collection. WARP does not reject it because it exceeds an illustrative example, but removing that policy cap does not make processing free or instantaneous. Plan for browser time, memory, evidence storage and, if enabled, WAVE charges. Acquisition itself does not use LLMs. Run a pilot before committing a large collection.

The URL list is stored as MySQL `LONGTEXT`, including an automatic widening migration for older installations. The HTTP request byte budget is configured by `MAX_DATASET_UPLOAD_BYTES` (default 1,610,612,736 bytes); individual form fields use that same budget, rather than Flask's smaller default. Local archive byte/path protections still apply. Database packet limits, available RAM/disk, proxy request limits and deployment timeouts can also constrain a very large submission. Configure these deployment resources for the planned workload.

Submit large collections through the background evaluation workflow. The job persists independently of the browser, and pause/resume remain available. The supplied deployment uses one worker; see [scheduling](../technical/jobs.md#scheduling-order) for its processing order.

## Fresh versus reused observations

With reuse enabled, WARP looks for a completed compatible record rather than performing an unnecessary new visit. The signature includes evaluation controls such as tool selection, Axe standard and dynamic-page timing. Reused records retain source identifiers and their original evaluation date; their copy does not represent a fresh visit on the composition date.

Disable reuse when your research question requires a current measurement. Check provenance in the report before treating any collection as a single-time snapshot of the web.

## Progress and pause

The worker processes requested URLs and commits evidence as it progresses. You can leave the list/report and return later. **Pause** stops scheduling additional observations at a safe boundary; it does not necessarily abort a browser already acquiring a page. **Resume** continues the remaining work and can apply the recovery behavior recorded for a Tranco evaluation.

Recorded processing seconds are not necessarily the elapsed wall-clock duration. Reused results incur no new browser evaluation in that copy. Interruptions and retries must be interpreted through their own records, not reconstructed from an assumed average.

## What is retained

Successful results can include rendered source HTML, response HTML when available, a screenshot, raw Axe/Lighthouse reports, optional WAVE output, page features and acquisition metadata. Completeness depends on the actual tool response and the acquisition type. Confirm the artifacts rather than assuming a completed counter guarantees every file is present.

Acquisition failures and incomplete tool responses appear with their status and error details. WARP's quality/recovery handling is described in [Evaluation pipeline](../technical/evaluation.md) and [Jobs and recovery](../technical/jobs.md).

## Practical pilot

Before launching hundreds of pages, evaluate a small set covering the page types you expect. Inspect lazy-loaded content, screenshot completeness, evidence files and per-page duration. Adjust the acquisition settings if warranted, record the changes, and then keep the policy fixed for the main cohort.
