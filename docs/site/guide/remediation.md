# Remediation

A remediation run starts from a completed result with a readable stored HTML snapshot. A11yResearch preserves that source, creates separate candidates and remeasures them. It does not edit the remote website.

## Submit a run

1. Open **New remediation** and find the acquired page.
2. Choose an explicit model/reasoning option.
3. Select iterative agentic execution or the independent zero-shot baseline.
4. For iterative execution, choose the intervention level.
5. Decide whether adaptive RAG-ACT grounding is enabled.
6. Review the displayed recipe and submit.

The source record, model snapshot and applicable targets are retained with the run. Cloud calls can incur charges. Test one representative page before submitting a large cohort.

## Five intervention policies

| Level | Policy | Allowed intervention |
| ---: | --- | --- |
| 1 | Minimal patches | Attributes, small insertions and narrowly scoped CSS; no element replacement or layout restructuring |
| 2 | Localized repair | Individual defective elements and small semantic replacements; no replacement of entire content regions |
| 3 | Coordinated repair | Root-cause/component planning, coordinated HTML/CSS and local keyboard behavior without redesigning the page |
| 4 | HTML regeneration | Generate a complete page from the acquired HTML using a selected design base; later refinements are localized |
| 5 | Markdown regeneration | Generate a complete page from quality-checked Markdown and retained content evidence; later refinements are localized |

A11yResearch validates generated operations against the selected policy before applying them. For example, minimal patches allow local changes while rejecting element replacement and global body/HTML CSS overrides.

For regeneration, the web module offers Bootstrap, Pico and Bulma design bases. The extension uses Bootstrap. A regeneration run retains the initial complete generation and can refine it without discarding the best measured candidate.

## Execution modes

**Iterative ATPGE** coordinates Acquire, Transform, Prompt, Generate and Evaluate, with deterministic decisions about refinement and retention. The selected intervention determines how much the page can change.

**Zero-shot — single call** provides an independent baseline: one generation followed by validation and measurement, without adaptive RAG-ACT retrieval or iterative refinement. Its report includes the generated candidate and any validation or measurement errors.

## Shared targets and resource limits

Targets are configurable under General settings and remain constant across intervention levels. Defaults are Lighthouse ≥94 and Axe ≤3. They are frozen at submission.

The same **Remediation targets → Resource limits per run** panel exposes the
iteration limit and cost/time limits. These apply to every intervention level;
moving the model or intervention slider does not change the resource limits.
Limits apply to each run, not the total charges or duration of a multi-page study.

The initial limits are **3 iterations, US$0.25 and 360 seconds per run**, shared
by all five levels and all model-slider positions. These are configurable
continuation limits, not a price assigned to a model or intervention. Actual
charges depend on provider usage; local Ollama has no cloud API charge.

Single-call modes retain one
iteration regardless of the configured iteration limit. Cost/time thresholds
control continuation after actual calls; they cannot guarantee an exact maximum
provider bill. Some calls or evaluation work can finish after a threshold is
crossed. Effective limits are frozen when a web run or extension request is
submitted, even if acquisition completes after Configuration changes.

### Level-specific recipe temperature

Only the intervention recipe below varies with this slider; the shared targets
and resource limits above remain unchanged.

| Level | Policy | Recipe temperature |
| ---: | --- | ---: |
| 1 | Minimal patches (default) | 0.05 |
| 2 | Localized repair | 0.20 |
| 3 | Coordinated repair | 0.50 |
| 4 | HTML regeneration | 0.50 |
| 5 | Markdown regeneration | 0.50 |

Zero-shot uses temperature 0.20. Temperature is sent only when supported by the
selected model's saved capabilities; the run records its effective settings.

## Outcomes and warnings

In **Remediation runs**, choose **Table** or **Cards** beside the filter.
This preference is shared with **Evaluations**. Both layouts show the same
stored results, with small **View report** and **Delete** actions below each
record. Active runs update in either view without losing the filter; deletion
still requires confirmation and is disabled while a run is queued or running.

The report distinguishes **accepted** (configured targets reached) from **completed with warnings** (a measured candidate retained without target attainment), and failures with no usable completed result. Inspect the recorded decision, retained candidate and actual evidence.

An active report updates automatically while retaining expanded evidence panels.
Original and retained-candidate scores have equal visual weight. **Content
retention** summarizes the equally weighted mean of recorded word, link, image
and banner/media retention percentages. If a measure is absent, the displayed
count identifies how many are included. The detail table shows source/candidate
counts and each retained percentage; banner/media candidate counts refer to
original resources found there. The summary does not change acceptance or
candidate ranking. DOM divergence measures structural change. Neither measure
certifies behavioral equivalence. **Compare
with original** opens the pair's report and reuses it on subsequent clicks.

A regression does not replace a better evaluated candidate merely because it is newer. Ranking considers target distance first, then retained content, with a visual tie-break for repair levels 1–3. See [runtime](../technical/agent-runtime.md) and [preservation measurements](../technical/preservation.md).

## A controlled experiment

A controlled study can hold the source cohort and targets fixed while varying the model, reasoning, intervention or retrieval condition. Source links, run settings, pair counts and warnings support comparisons of the resulting candidates.
