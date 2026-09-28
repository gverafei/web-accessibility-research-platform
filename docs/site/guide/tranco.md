# Seeded Tranco sampling

Tranco supplies the ranking frame, while WARP supplies a deterministic selection and acquisition procedure. A domain's rank is a popularity-group indicator, not its accessibility score.

## UI workflow

Choose **Tranco** in New acquisition. The form obtains the latest standard top-million list, resolves its permanent list identifier and records a SHA-256 digest of the downloaded frame. Enter a seed and the target counts for enabled strata. The ordinary UI does not require a manually uploaded ranking file.

| Bundled UI stratum | Rank interval | Maximum target |
| --- | --- | ---: |
| Global top 500 | 1–500 | 100 |
| Very high popularity | 501–5,000 | 200 |
| High popularity | 5,001–50,000 | 200 |
| Medium popularity | 50,001–250,000 | 200 |
| Popularity tail | 250,001–1,000,000 | 200 |

Those maxima give the 900-page example. A zero count disables a stratum. For each enabled group, the submission also creates an ordered reserve, normally at least 10 candidates and otherwise matching the requested target count.

## Reproducible ordering

`sample_tranco` sorts candidates by a SHA-256 key derived from the procedure version, list ID, seed, stratum label, rank and domain. The first candidates become selected observations and the following candidates become the reserve. Identical inputs therefore produce the same ordering without depending on a particular Python random-number implementation.

Pin the **list ID, digest, seed, boundaries, target counts and procedure version**. A repeated seed against tomorrow's ranking is not the same sample.

## Recovery and replacement

The evaluation actions allow retrying failed candidates, replacing failures from the same stratum, and filling vacancies after curation. WARP uses the stored reserve/order rather than inventing a convenient replacement from another group.

Keep technical failure, content exclusion and reserve substitution distinguishable. Never exclude a page because its accessibility score is high or low, its language differs from yours, or another tool reports a different result. Content eligibility is a study decision that should be defined before the final analysis.

Download the sampling manifest from the evaluation to inspect selected/reserve roles, ranks and acquisition outcomes. Review flagged cases and evidence completeness before declaring a collection ready for release.

## Offline code example

This synthetic example exercises the selector without accessing Tranco, starting browsers or making paid calls:

```python
# docs-test: offline
from tranco_sampling import sample_tranco

ranking = [(rank, f"site{rank}.example.org") for rank in range(1, 501)]
counts = {
    "rank_1_500": 2, "rank_501_5000": 0, "rank_5001_50000": 0,
    "rank_50001_250000": 0, "rank_250001_1000000": 0,
}
reserves = {key: (2 if count else 0) for key, count in counts.items()}
candidates, strata = sample_tranco(ranking, "EXAMPLE", "pilot-42", counts, reserves)
selected = [item for item in candidates if item["role"] == "selected"]
assert len(selected) == 2
assert (candidates, strata) == sample_tranco(
    ranking, "EXAMPLE", "pilot-42", counts, reserves
)
```

Run with `PYTHONPATH=web/app` and the web dependencies installed. This is a demonstration of the implementation, not a statistically meaningful web sample.

## Custom sampling designs

The Python selector also accepts custom rank intervals through `strata_definitions`, independently of the web form's defaults. Supply disjoint `(label, display_name, lower_rank, upper_rank)` tuples and per-label sample/reserve counts to `sample_tranco`. Retain these definitions, the pinned ranking and the seed with the resulting manifest. Unequal allocation needs design-aware weighting for population estimates; see [dataset construction](datasets.md).
