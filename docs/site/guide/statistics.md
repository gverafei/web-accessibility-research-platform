# Statistics and visualizations

A11yResearch provides descriptive analysis to help researchers inspect collections and compare runs. The software does not automatically turn a purposive or unequally allocated cohort into a representative estimate of the entire web.

## Summaries and missing values

Means, medians and sample standard deviations are calculated from available values. Some display helpers return zero for an empty list or a standard deviation with fewer than two observations; that display convention is not evidence that an unmeasured population quantity is zero. Check sample counts and exported missing values.

Charts requiring two measurements use complete pairs. The correlation record exposes the pair count; Pearson and Spearman values require at least three valid pairs, and fewer than ten are marked exploratory. Constant variables cannot produce a defined correlation.

## Issue density

For a page with `a` Axe instances and `d > 0` DOM nodes:

```text
Axe density = 1000 × a / d
Weighted impact density = 1000 × (4×critical + 3×serious + 2×moderate + minor) / d
```

These normalize counts by a recorded page-size feature. They are descriptive engineering measures, not an accessibility probability or validation of the impact weights.

## Plots

Scatterplots compare raw measurements on linear axes, with graph-specific colors and dark point borders. A densely populated area can contain many overlapping pages. The legend represents the series; it is not another observation.

Distribution plots show medians, quartiles, 1.5×IQR whiskers and outliers. Axe distribution displays can use a `log1p` transformation for readability while retaining original-count labels. Summary statistics use the recorded values independently of the display scale.

The Tranco summary bars show **mean WCAG Axe issue instances per completed
page** and **mean Lighthouse score** in each stratum. Both are arithmetic means,
so a larger stratum does not appear worse merely because it contributes more
pages. They describe observed pages, not frame-weighted population estimates.

Numeric bars show their values directly wherever there is room, including zero
and negative values. Dense charts and very small stacked segments retain
tooltips to avoid overlapping labels. Light-theme labels have no white backing;
both themes use the shared chart-label component.

## Cross-tool ranking

For at least three complete observations, A11yResearch converts tool results to within-study percentile ranks with averaged ranks for ties. Axe is oriented so fewer instances are better; Lighthouse (and WAVE AIM when included) are oriented so higher is better. The composite is the mean of the included percentile components.

```text
Percentile = 100 × (m − favorable_rank) / (m − 1)
Composite = mean(included tool percentiles)
```

This ranks the current collection. It is neither a universal scale nor a replacement for the raw tool results. Adding/removing pages changes the percentile reference cohort.

## Paired results

Use original/candidate identity links, not merely group means. Axe reduction is `original − candidate`; Lighthouse gain is `candidate − original`. Report improved, unchanged and worsened pairs along with mean/median changes and available pair denominators.

## Population-oriented analysis

For disproportionate strata, preserve `N_h`, `n_h` and inclusion/replacement rules. A design-aware mean uses `Σ (N_h/N) × mean_h`; uncertainty depends on variation within each stratum and the sampling fraction. The report's ordinary sample mean is not that weighted estimate. See [Building research datasets](datasets.md) before making broader claims.
