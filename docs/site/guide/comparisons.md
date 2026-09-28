# Paired comparisons

Comparison studies place original observations and generated candidates into labeled groups. Their purpose is to help inspect changes while preserving the identity of each source, not to imply that unmatched group means are paired evidence.

## Create a comparison

Use **Comparisons** to create a study from stored evaluation results and/or remediation runs. A remediation report also offers an action to compare a run with its original. Give the study and group labels a meaning that is clear in exports.

For a stratified remediation demonstration, keep five original groups and their five corresponding remediated groups. Each candidate must join to the same source result used for generation. A coincidentally identical domain name is not sufficient when multiple acquisitions exist.

## Measures to read together

| Measure | Interpretation |
| --- | --- |
| Original/candidate group mean | Description of that group's available measurements |
| Complete paired count | Number with the measurements required for the paired change |
| Axe reduction | Original instances minus candidate instances |
| Lighthouse gain | Candidate score minus original score |
| Improvement percentage | Relative change where the original denominator is usable |
| Improved/unchanged/worsened | Direction counts over complete pairs |
| Cost and time | Recorded charges and processing durations, not a future price forecast |

The report exposes group summaries and per-page changes. Interpret zero original Axe counts carefully: a relative reduction can be undefined even when an absolute difference is meaningful.

## Warnings are part of the comparison

Target attainment and candidate availability are separate. A retained candidate with warnings can still supply measured evidence if included under your protocol. Do not silently remove it to make the average look better. State the inclusion rule and compare the corresponding original denominator.

## Example protocol

Select 25 observations independently within each of five stored strata using a recorded seed, after explicit content/technical eligibility review. Freeze the 125 sources. Apply one model/reasoning, one intervention policy and the same targets. Then compare each retained candidate with its own original.

That is a demonstration of within-stratum paired analysis, not a population estimate or a strategy ranking. To compare interventions causally, predefine allocation, replicated runs, stochastic controls and analysis. A single successful cohort is not evidence that every model or level would behave the same way.

## Editing a study

Group names, display names, ordering and baseline selection are editable without changing raw stored measurements. Deleting a comparison member changes the analysis cohort. Record that change and confirm it was not based on the observed outcome.

The comparison implementation is in `routes/comparisons.py`. See [statistics](statistics.md) for rank/density summaries and [storage](../technical/storage.md) for source/run/member links.
