# Building research datasets

WARP helps turn a costly sequence of browser visits, accessibility measurements and evidence collection into a reusable corpus. Its value is not that any small sample necessarily reproduces the entire web; it is that a declared protocol can be executed and its evidence retained for further experiments.

## Define the estimand and scope

Decide whether the corpus describes the released pages, compares popularity strata, supports paired remediation, or estimates a property of a defined ranking population. Those goals can require different allocations and analyses.

Define content eligibility, acquisition success, required artifacts, replacement rules and the ranking date before reviewing accessibility scores. An inability to acquire a domain can create nonresponse bias that a larger sample alone does not remove.

## Run an acquisition pilot

Use a bounded pilot to estimate successful acquisition rates, retries, artifact completeness and per-stratum duration. Separately estimate the variation of the actual outcome you intend to analyze.

The acquisition-success proportion is not automatically the `p` in a sample-size calculation for accessibility prevalence. Likewise, continuous outcomes such as mean issue count need a variance-based precision calculation, not a binary proportion formula.

## Choose allocation deliberately

The bundled UI supports independent counts in five popularity strata, up to 900 pages in total. The Python selector also supports custom strata and allocations. Choose counts to balance group-level analysis, acquisition cost and full-frame precision, and retain the design in the sampling manifest. The interface's default limits are not a statistical sample-size recommendation or fixed percentages of each stratum.

For a stratified probability design:

```text
W_h = N_h / N
Estimated population mean = Σ W_h × mean_h
Estimated variance = Σ W_h² × (1 − n_h/N_h) × s_h²/n_h
```

These expressions assume the corresponding within-stratum sampling design and usable inclusion information. Reserve substitution/content filtering complicates which population the final observed corpus represents. Describe that process and its limitations rather than claiming weights eliminate all bias.

For a binary outcome, conservative `p=q=0.5` maximizes the simple-random-sample reference variance. A pilot can inform a different outcome-specific value, but do not replace it with a technical success rate for a different question. A reference margin from a simple-random formula is not a guarantee for every stratum or a disproportionate weighted estimate.

## Curate and validate evidence

Retain valid pages regardless of their score, language or disagreement across tools. Review challenge/error/incomplete pages and defined out-of-scope content. Replace only ineligible observations through the predeclared same-stratum reserve, keeping a recoverable provenance trail.

Before release, validate target counts, source HTML, screenshots, raw reports, tool versions, content digests and provenance. Categorize only after technical validation and review the inferred labels. Excluded research evidence should not be publicly exposed merely because it is retained internally for audit.

## Prepare a reusable release

Provide a data dictionary, sampling manifest, source revision, non-secret configuration, artifact checksums, machine-readable measurements, reproduction scripts and an explanation of missingness/eligibility. Observe the captured material's licensing and privacy restrictions.

A `.warp` export supports reuse of evaluation evidence; it is not itself the whole publication protocol. Keep the release package and the software documentation linked but distinct.

## Report resources honestly

Sum recorded processing seconds and actual provider charges separately from elapsed wall time. Reused results and interrupted work have different accounting. An extrapolation to one million pages must identify assumptions, uncertainty and fixed/variable costs; do not promise equivalent results or invent unrecorded attempt durations.
