# Building research datasets

WARP helps turn a costly sequence of browser visits, accessibility measurements and evidence collection into a reusable corpus. Its value is not that any small sample necessarily reproduces the entire web; it is that a declared protocol can be executed and its evidence retained for further experiments.

## Define the estimand and scope

Decide whether the corpus describes the released pages, compares popularity strata, supports paired remediation, or estimates a property of a defined ranking population. Those goals can require different allocations and analyses.

A collection protocol specifies content eligibility, acquisition success, required artifacts, replacement rules and the ranking date. Acquisition success rates help characterize coverage and nonresponse.

## Run an acquisition pilot

Use a bounded pilot to estimate successful acquisition rates, retries, artifact completeness and per-stratum duration. Separately estimate the variation of the actual outcome you intend to analyze.

The acquisition-success proportion is not automatically the `p` in a sample-size calculation for accessibility prevalence. Likewise, continuous outcomes such as mean issue count need a variance-based precision calculation, not a binary proportion formula.

## Choose allocation deliberately

The bundled UI supports researcher-defined, independent counts in five popularity strata, with no example-specific sample-size cap. Each target must fit the available domains in its rank interval. The Python selector also supports custom strata and allocations. Choose counts to balance group-level analysis, acquisition cost and full-frame precision, and retain the design in the sampling manifest. The form's initial values are not a statistical sample-size recommendation or fixed percentages of each stratum.

Selecting an entire stratum leaves no unused replacement candidates. If some domains remain unrecoverable, retain the requested target and report the achieved count and nonresponse separately; do not expand the interval or replace them from another stratum without declaring a new design. The [Tranco recovery policy](tranco.md#when-a-stratum-cannot-reach-its-target) explains this boundary.

For a stratified probability design:

```text
W_h = N_h / N
Estimated population mean = Σ W_h × mean_h
Estimated variance = Σ W_h² × (1 − n_h/N_h) × s_h²/n_h
```

These expressions use within-stratum sample means, variances and sampling fractions. Eligibility and replacement records help establish which population the observed corpus represents; weights account for allocation, while nonresponse is considered separately.

For a binary outcome, `p=q=0.5` gives the maximum simple-random-sample reference variance. A pilot can estimate an outcome-specific proportion. Technical acquisition success and accessibility prevalence are different outcomes, each with its own proportion and precision calculation.

## Curate and validate evidence

Review capture completeness and apply the study's content-eligibility criteria. The report exposes challenge/error responses and acquisition metadata to support that review. Tranco vacancies can be filled from the declared same-stratum reserve, with replacement provenance retained in the manifest.

Before release, validate target counts, source HTML, screenshots, raw reports, tool versions, content digests and provenance. Categorize only after technical validation and review the inferred labels. Excluded research evidence should not be publicly exposed merely because it is retained internally for audit.

## Prepare a reusable release

Provide a data dictionary, sampling manifest, source revision, non-secret configuration, artifact checksums, machine-readable measurements, reproduction scripts and an explanation of missingness/eligibility. Observe the captured material's licensing and privacy restrictions.

A `.warp` export lets collaborators reuse evaluation evidence. A dataset release can complement it with the data dictionary, analysis routines and study protocol.

## Report resources honestly

Recorded processing seconds and provider charges are separate from elapsed wall time. Reuse and interruption records explain which work contributes to each total. Per-stratum pilot durations can support workload planning when reported alongside the acquisition conditions and observed variability.
