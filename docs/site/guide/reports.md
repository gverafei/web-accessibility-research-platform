# Evaluation reports

Open a completed evaluation from **Evaluations**. A11yResearch prepares its collection-level analysis and displays a loading view while a large report is being assembled.

Next to the list filter, choose **Table** or **Cards**. The display preference
is shared with **Remediation runs** and remembered in this browser. Both views
use the same records and filters. Compact, labelled actions sit beneath each
record; use **View report**, rather than double-clicking a row. A globe identifies
**Web URLs** as an acquisition source, not an external navigation action.

The top search bar finds evaluation names, URLs/domains, status (such as
`completed` or `running`) and origin (`imported` or `composed`). Click a
suggestion to open its report through the loading view; a URL result takes you
to URL-level evidence. Press Enter to list matching evaluations. Searches use
stored records and do not acquire or evaluate pages again.

## URL measurement matrix

The matrix supports filtering, sorting and pagination. Each row ties a page's URL and thumbnail to its measurements and provenance. Use the thumbnail preview to inspect captured content; use the URL link to open the current website, remembering that it may no longer match the stored page.

Depending on the experiment, the matrix includes Axe issue/severity counts, Lighthouse score, Tranco rank/stratum, category, evaluation date and source/provenance information. A dash denotes missing information, not a zero.

## Measurements

- **Axe issues:** reported affected-node instances, summed across selected WCAG-tagged rules, excluding Best Practices. A DOM node can occur in more than one rule; the optional Best Practices column is separate.
- **Critical/serious/moderate/minor:** the reported impact classification, not a separate manual user assessment.
- **Lighthouse:** the accessibility score on its native 0–100 scale.
- **WAVE:** optional independent API measurements, present only when that tool was requested and returned usable evidence.
- **Page features and runtime:** structural/content characteristics and recorded processing time, when available.

Use the raw artifacts to interpret unexpected numbers. A zero from a real evaluated page and missing evidence from a failed acquisition are different cases.

## Available analyses

Reports summarize the collection, popularity strata where present, issue distributions, tool relationships, page complexity/runtime relationships and within-study cross-tool ranking. Read [Statistics and visualizations](statistics.md) before treating those summaries as population estimates.

Graphs use the same underlying stored observations as the matrix, but an individual graph can require a smaller complete-case subset. Its pair count matters. Outliers are data, not an automatic reason to remove a page.

## Downloads

The evaluation actions offer a CSV table and a portable `.warp` export. The report can expose raw Axe/Lighthouse/WAVE JSON and screenshots for specific rows. A Tranco evaluation also provides its sampling manifest.

CSV is convenient for analysis but is not an artifact-complete backup. Use `.warp` for evaluation exchange and a full storage backup for the whole installation, including remediation/comparison records.

## Review before analysis

An evaluation cannot be deleted while queued/running or while remediation runs
use its stored pages. A blocked deletion reports the dependent run count and
IDs. Keep the evaluation if those runs are needed. Otherwise, remove the runs
from any comparisons that use them, then delete the runs before deleting the
source evaluation. Dependencies are not deleted automatically.

Verify that the intended source cohort is present, evidence files exist, duplicates/provenance are understood and all exclusions follow the declared protocol. When a page is technically invalid, diagnose and recover it; when it is valid but performs poorly, retain it.

The report is designed for expert inspection, not to replace review of the website's functions or a study's inferential design.
