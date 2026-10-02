# Adaptive ACT retrieval

ACT grounding supplies relevant accessibility examples to later refinements. The researcher controls this optional retrieval condition when submitting a remediation run.

## What the switch means

In the web remediation form, ACT grounding is enabled by default. The extension exposes its own optional evidence switch. Enabled means retrieval is **armed**; it does not mean examples were used in every iteration.

The first generation is unchanged by adaptive ACT retrieval. A later iteration can activate it when actual Axe/Lighthouse findings justify refinement. With the switch off, no ACT retrieval is used for that run. Zero-shot execution disables it.

The trace records enabled, activated, retrieved and supplied evidence separately. Compare actual use, not just the UI switch, when studying RAG.

## Corpus and provenance

The synchronization routine loads approved passed/failed examples from W3C ACT material and retains rule/testcase identifiers, source URLs, snapshot digest, retrieval time and license provenance. A separate supplement contains platform-authored pairs grounded in primary guidance; those are explicitly **not official ACT testcases**.

The iteration trace distinguishes W3C material from complementary guidance and links each supplied example to its source.

## Retrieval implementation

A11yResearch uses a local 384-dimensional feature-hashing representation and Qdrant cosine search, followed by lexical/concept checks. It does not call a paid embedding model. Exact mappings connect measured Axe rules to relevant ACT concepts.

Retrieved context is bounded. The routine favors complete positive/negative pairs for a matched rule and excludes examples that exceed the context budget. If no relevant complete evidence is available, the trace records an empty retrieval.

## Initialize or update the corpus

To initialize or replace the retrieval corpus:

```bash
docker compose exec worker python sync_act_rag.py
```

The command downloads the upstream snapshot, recreates the configured ACT collection and loads the supplement. It replaces any custom collection at that location, so a backup is useful before updating. Running it between cohorts keeps the retrieval snapshot consistent within each cohort.

To inspect availability without modifying the corpus, use the application's remediation panel or call `status()` from `web/app/remediation_rag.py` inside the service.

## If retrieval is unavailable

When the vector service or relevant examples are unavailable, remediation can still retain an evaluated candidate. The trace records retrieval availability and the context actually supplied. Check service connectivity and corpus status to diagnose an empty retrieval.

The technical boundaries are covered in [Agent runtime](../technical/agent-runtime.md); the retrieval functions are mapped in the [source reference](../reference/source-map.md).
