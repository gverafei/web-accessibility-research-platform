# Your first experiment

This walkthrough starts with ordinary web evaluation and then demonstrates one remediation. The first part does not require an AI account.

## 1. Acquire two public pages

Open **New acquisition**, select URL acquisition, and enter:

```text
https://example.org/
https://www.w3.org/
```

Give the experiment a descriptive name. Leave WAVE off. For a genuinely new measurement, disable reuse of existing results; with reuse enabled, a compatible stored result can be copied instead of visiting the page again.

Submit the form. WARP creates a queued evaluation and its worker acquires the pages. The web application remains usable while the browser work runs. Navigate to **Evaluations** to inspect progress or pause the job.

## 2. Inspect the report

Open the completed evaluation. The report initially displays a loading state when preparing a large analysis. Check:

- The URL measurement matrix, including thumbnails and individual measurements.
- The available source HTML, raw tool reports and environment metadata.
- The charts and their sample counts. Missing measurements are not successful zero-issue results.

If acquisition fails, use the recorded error and [troubleshooting guide](../reference/troubleshooting.md). Do not interpret a browser/network failure as an accessibility finding.

## 3. Configure one model

For cloud repair, set the OpenRouter API key under **Configuration → General**. Review the enabled choices under **Model catalogue**, and save that tab separately.

For local repair, configure **Local LLM (Ollama)**, refresh its installed models, choose one and test it. Docker must be able to reach the configured Ollama address. A local-only installation never silently switches to a cloud model.

## 4. Submit one remediation

Open **New remediation** and choose a completed source with stored HTML. Select an explicit model, choose **Iterative ATPGE**, and leave the intervention at **Minimal patches**. Review the shared research targets. Decide whether ACT grounding should be enabled for this experiment.

Submit only one page first. Cloud repair is a paid operation. The configured cost/time controls bound continuation, not an exact prepayment limit; a completed provider call can put the recorded cost above the threshold.

## 5. Read the evidence

The remediation report exposes the retained candidate, its target status, the [iteration trace and activity log](../guide/evidence.md). Inspect the page as well as its scores. A candidate with warnings is distinct from one reaching the configured targets.

Use the comparison action to pair the candidate with its original. Export the original evaluation as a `.warp` package if you want to share the acquired evidence with a collaborator.

## Next steps

For a larger study, use [Tranco sampling](../guide/tranco.md), document your [sampling and curation protocol](../guide/datasets.md), and hold the model/targets/policy fixed across paired runs. The guide to [comparisons](../guide/comparisons.md) explains how WARP keeps those pairs aligned.
