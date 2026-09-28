# Seeded Tranco sampling

Tranco is a ranking of popular domains designed for web research. Visit the [official Tranco website](https://tranco-list.eu/) to learn about its methodology and download current or archived lists.

Tranco supplies the ranking frame, while WARP supplies a deterministic selection and acquisition procedure. A domain's rank is a popularity-group indicator, not its accessibility score.

## UI workflow

Choose **Tranco** in New acquisition. The form obtains the latest standard top-million list, resolves its permanent list identifier and records a SHA-256 digest of the downloaded frame. Enter a seed and the target counts for enabled strata. The ordinary UI does not require a manually uploaded ranking file.

| Bundled UI stratum | Rank interval |
| --- | --- |
| Global top 500 | 1–500 |
| Very high popularity | 501–5,000 |
| High popularity | 5,001–50,000 |
| Medium popularity | 50,001–250,000 |
| Popularity tail | 250,001–1,000,000 |

Choose independent whole-number counts for your study. WARP imposes no fixed per-stratum or total observation-count cap: the target in a group must not exceed the domains available in that interval of the pinned ranking. A zero count disables a stratum. The values initially shown in the form are editable starting values, not a prescribed study design.

For each enabled group, WARP requests an ordered reserve of at least 10 candidates or the target count, whichever is larger. It records only the **unused domains actually available** in that group. Selecting all domains in an interval is allowed, but leaves no reserve; reserving candidates never reduces the requested primary target. Large collections require correspondingly more processing time, memory and disk space. See [acquisition capacity](acquisition.md#collection-size-and-resource-planning).

## Reproducible ordering

`sample_tranco()` in `web/app/tranco_sampling.py` sorts candidates by a SHA-256 key derived from the procedure version, list ID, seed, stratum label, rank and domain. The first candidates become selected observations and the following candidates become the reserve. Identical inputs therefore produce the same ordering without depending on a particular Python random-number implementation.

Pin the **list ID, digest, seed, boundaries, target counts and procedure version**. A repeated seed against tomorrow's ranking is not the same sample.

## Recovery and replacement

The evaluation actions support retrying failed candidates, replacing failures within the same stratum and filling vacancies after curation. Replacement follows the stored candidate order.

The sampling manifest distinguishes technical failures, content exclusions and reserve substitutions. Content eligibility is defined by the researcher's study protocol; accessibility scores, language and cross-tool differences remain available for analysis.

Download the sampling manifest from the evaluation to inspect selected/reserve roles, ranks and acquisition outcomes. Review flagged cases and evidence completeness before declaring a collection ready for release.

### When a stratum cannot reach its target

WARP retries each unsuccessful website acquisition once. If it still fails, recovery uses the next unused candidate from the **same interval, pinned list and deterministic order**. When the initially recorded reserve runs out, WARP can extend it with still-unused domains from that same stratum. It never borrows domains from another stratum or silently switches ranking releases.

If all eligible ranked candidates in that interval have already been tried, recovery ends for that group. Work in other groups continues. The worker eventually finalizes the evaluation with the successful observations retained and an **incomplete dataset** warning; `completed` is the processing lifecycle status, not a guarantee that all targets were achieved. The report keeps target and final counts separate, and failed URLs/error context remain available outside the valid measurement cohort.

For example, selecting all 500 domains ranked 1–500 leaves no reserve. If only 300 succeed after the controlled retries, the final count is **300 out of a target of 500**, with 200 unresolved failures. The target is not silently reduced to 300, those failures are not counted as zero-issue pages, and rank 501 is not used as a replacement. A later researcher-requested retry may recover more pages, but cannot guarantee 500 successes. Redefining the interval or choosing a newer ranking requires an explicit new sampling design, not an automatic substitution.

An evaluator/service interruption is different: WARP retains the candidate and requeues the work rather than consuming its website retry. A temporarily unavailable pinned ranking is likewise not evidence that the domain pool is exhausted. See [jobs and recovery](../technical/jobs.md).

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
