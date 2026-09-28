# Paired comparisons

Comparison studies place original observations and generated candidates into labeled groups. Their purpose is to help inspect changes while preserving the identity of each source, not to imply that unmatched group means are paired evidence.

## Create a comparison

Use **Comparisons** to create a study from stored evaluation results and/or remediation runs. A remediation report also offers an action to compare a run with its original. Give the study and group labels a meaning that is clear in exports.

For a stratified comparison, create original and remediated groups for each stratum in the study. Candidate-to-source links identify the acquisition used for generation, including cases where a domain has multiple stored captures.

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

A retained candidate can have valid measurements while remaining below a target. Warning status and complete-pair counts help apply a consistent inclusion rule and interpret the comparison denominator.

## Example protocol

Select observations independently within the study's strata using a recorded seed and the desired group sizes. Apply a model/reasoning choice, intervention policy and targets to the frozen sources, then compare each retained candidate with its own original.

This setup supports within-stratum paired analysis. A study comparing intervention strategies can extend it with randomized allocation, replicated runs and a predefined analysis plan.

## Editing a study

Group names, display names, ordering and baseline selection are editable without changing raw measurements. Adding or removing members updates the analysis cohort and its pair counts.

The comparison implementation is in `routes/comparisons.py`. See [statistics](statistics.md) for rank/density summaries and [storage](../technical/storage.md) for source/run/member links.
