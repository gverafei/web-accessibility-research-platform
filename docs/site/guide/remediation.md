# Remediation

A remediation run starts from a completed result with a readable stored HTML snapshot. WARP preserves that source, creates separate candidates and remeasures them. It does not edit the remote website.

## Submit a run

1. Open **New remediation** and find the acquired page.
2. Choose an explicit model/reasoning option.
3. Select iterative agentic execution or the independent zero-shot baseline.
4. For iterative execution, choose the intervention level.
5. Decide whether adaptive ACT grounding is enabled.
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

WARP validates generated operations against the selected policy before applying them. For example, minimal patches allow local changes while rejecting element replacement and global body/HTML CSS overrides.

For regeneration, the web module offers Bootstrap, Pico and Bulma design bases. The extension uses Bootstrap. A regeneration run retains the initial complete generation and can refine it without discarding the best measured candidate.

## Execution modes

**Iterative ATPGE** coordinates Acquire, Transform, Prompt, Generate and Evaluate, with deterministic decisions about refinement and retention. The selected intervention determines how much the page can change.

**Zero-shot — single call** provides an independent baseline: one generation followed by validation and measurement, without adaptive ACT retrieval or iterative refinement. Its report includes the generated candidate and any validation or measurement errors.

## Shared targets and level-specific recipe

Targets are configurable under General settings and remain constant across intervention levels. Defaults are Lighthouse ≥94 and Axe ≤3. They are frozen at submission.

| Level | Iteration limit | Recipe temperature* | Cost continuation threshold | Time continuation threshold |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 3 | 0.05 | US$0.15 | 240 s |
| 2 | 3 | 0.20 | US$0.20 | 300 s |
| 3 | 3 | 0.50 | US$0.25 | 360 s |
| 4 | 3 | 0.50 | US$0.40 | 600 s |
| 5 | 3 | 0.50 | US$0.50 | 600 s |

*Temperature is included when supported by the selected model. The saved model capabilities determine which parameters are sent.*

The zero-shot recipe uses one iteration, temperature 0.20, US$0.15 and 240 seconds. Cost/time thresholds control continuation after actual calls; they cannot guarantee an exact maximum provider bill. Some calls or evaluation work can finish after a threshold is crossed.

## Outcomes and warnings

The report distinguishes **accepted** (configured targets reached) from **completed with warnings** (a measured candidate retained without target attainment), and failures with no usable completed result. Inspect the recorded decision, retained candidate and actual evidence.

A regression does not replace a better evaluated candidate merely because it is newer. Ranking considers target distance first, then retained content, with a visual tie-break for repair levels 1–3. See [runtime](../technical/agent-runtime.md) and [preservation measurements](../technical/preservation.md).

The five policies share target settings from **Configuration → General**. Each submitted run retains those targets together with its selected intervention and model.

## A controlled experiment

A controlled study can hold the source cohort and targets fixed while varying the model, reasoning, intervention or retrieval condition. Source links, run settings, pair counts and warnings support comparisons of the resulting candidates.
