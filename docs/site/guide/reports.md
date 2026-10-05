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

### Result counts and unique URLs

The dashboard's **Completed page results** counts stored results with completed
status. The **Stored page results** total in Evaluations also includes failed
attempts. Both count records across collections, including reused, imported and
combined copies; they do not count distinct URLs or new acquisition calls.
The dashboard's Lighthouse average likewise includes completed result copies.
**Manage URLs** groups completed results by normalized URL and shows the latest
one per URL. Its **unique URLs** total can therefore be smaller. Filtering that
catalogue shows the number of matching unique URLs, not the total across all
evaluations. No stored results are removed by this grouping.

### Inspecting individual observations

The matrix supports filtering, sorting and pagination. Each row ties a page's URL and thumbnail to its measurements and provenance. Use the thumbnail preview to inspect captured content; use the URL link to open the current website, remembering that it may no longer match the stored page.

The matrix includes each page's category for every acquisition source, including
URL batches, local HTML and imported or combined evaluations. The same category
appears in URL-level evidence; **Unclassified** means no category has been assigned.
Assign or correct categories in [Manage URLs](manage-urls.md), then reload the
report to see the saved values. Tranco rank and stratum appear only for Tranco
studies. Depending on the experiment, the matrix also includes Axe issue/severity
counts, Lighthouse score, evaluation date and source/provenance information.
A dash denotes missing information, not a zero.

## Measurements

- **Axe issues:** reported affected-node instances, summed across selected WCAG-tagged rules, excluding Best Practices. A DOM node can occur in more than one rule; the optional **Best-practice issues** column is separate and appears immediately after Axe issues when enabled in Configuration. Display switches apply to existing reports after saving and reloading, without rescanning; unavailable legacy counts appear as a dash.
- **Critical/serious/moderate/minor:** the reported impact classification, not a separate manual user assessment.
- **Lighthouse:** the accessibility score on its native 0–100 scale.
- **WAVE:** optional independent API measurements, present only when that tool was requested and returned usable evidence.
- **Page features and runtime:** structural/content characteristics and recorded processing time, when available.

Use the raw artifacts to interpret unexpected numbers. A zero from a real evaluated page and missing evidence from a failed acquisition are different cases.

## Available analyses

Reports summarize the collection, popularity strata where present, issue distributions, tool relationships, page complexity/runtime relationships and within-study cross-tool ranking. Read [Statistics and visualizations](statistics.md) before treating those summaries as population estimates.

Graphs use the same underlying stored observations as the matrix, but an individual graph can require a smaller complete-case subset. Its pair count matters. Outliers are data, not an automatic reason to remove a page.

## Downloads

The evaluation actions offer a CSV table and a portable `.warp` export. The
**URL-level evidence** panel offers raw Axe/Lighthouse/WAVE JSON and, when
stored, two HTML downloads alongside them: **Response HTML** is the initial page
response before browser rendering; **Rendered HTML** is the frozen rendered DOM
used for evaluation. They can differ after scripts and dynamic-content loading.
HTML is downloaded as a file, not executed inside the platform. These downloads
also use preserved artifacts in imported or combined collections; no new visit
or evaluation is performed. A Tranco evaluation provides its sampling manifest.

CSV is convenient for analysis but is not an artifact-complete backup. Use `.warp` for evaluation exchange and a full storage backup for the whole installation, including remediation/comparison records.

## Review before analysis

An evaluation cannot be deleted while queued/running or while remediation runs
use its stored pages. A blocked deletion reports the dependent run count and
IDs. Keep the evaluation if those runs are needed. Otherwise, remove the runs
from any comparisons that use them, then delete the runs before deleting the
source evaluation. Dependencies are not deleted automatically.

Verify that the intended source cohort is present, evidence files exist, duplicates/provenance are understood and all exclusions follow the declared protocol. When a page is technically invalid, diagnose and recover it; when it is valid but performs poorly, retain it.

The report is designed for expert inspection, not to replace review of the website's functions or a study's inferential design.
