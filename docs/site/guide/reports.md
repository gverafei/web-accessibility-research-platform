# Evaluation reports

Open a completed evaluation from **Evaluations**. WARP prepares its collection-level analysis and displays a loading view while a large report is being assembled.

## URL measurement matrix

The matrix supports filtering, sorting and pagination. Each row ties a page's URL and thumbnail to its measurements and provenance. Use the thumbnail preview to inspect captured content; use the URL link to open the current website, remembering that it may no longer match the stored page.

Depending on the experiment, the matrix includes Axe issue/severity counts, Lighthouse score, Tranco rank/stratum, category, evaluation date and source/provenance information. A dash denotes missing information, not a zero.

## Measurements

- **Axe issues:** reported affected-node instances, summed across included rules. A DOM node can occur in more than one rule.
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

Verify that the intended source cohort is present, evidence files exist, duplicates/provenance are understood and all exclusions follow the declared protocol. When a page is technically invalid, diagnose and recover it; when it is valid but performs poorly, retain it.

The report is designed for expert inspection, not to replace review of the website's functions or a study's inferential design.
