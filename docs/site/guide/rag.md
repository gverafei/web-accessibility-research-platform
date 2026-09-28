# Adaptive ACT retrieval

ACT grounding supplies relevant accessibility examples to later refinements. It is optional experimental evidence, not an independent agent that can decide whether a candidate is accepted.

## What the switch means

In the web remediation form, ACT grounding is enabled by default. The extension exposes its own optional evidence switch. Enabled means retrieval is **armed**; it does not mean examples were used in every iteration.

The first generation is unchanged by adaptive ACT retrieval. A later iteration can activate it when actual Axe/Lighthouse findings justify refinement. With the switch off, no ACT retrieval is used for that run. Zero-shot execution disables it.

The trace records enabled, activated, retrieved and supplied evidence separately. Compare actual use, not just the UI switch, when studying RAG.

## Corpus and provenance

The synchronization routine loads approved passed/failed examples from W3C ACT material and retains rule/testcase identifiers, source URLs, snapshot digest, retrieval time and license provenance. A separate supplement contains platform-authored pairs grounded in primary guidance; those are explicitly **not official ACT testcases**.

Do not relabel the supplement as W3C-produced data. Source attribution is part of the experimental record.

## Retrieval implementation

WARP uses a local 384-dimensional feature-hashing representation and Qdrant cosine search, followed by lexical/concept checks. It does not call a paid embedding model. Exact mappings connect measured Axe rules to relevant ACT concepts.

Retrieved context is bounded. The routine favors complete positive/negative pairs for a matched rule, excludes oversized sliced examples and can abstain when relevant complete evidence is unavailable. An empty retrieval is not permission to fabricate advice.

## Initialize or update the corpus

The following is an **administrator write operation**, not a health check:

```bash
docker compose exec worker python sync_act_rag.py
```

It downloads the current upstream snapshot, deletes/recreates the configured ACT collection and loads the supplement. Back up a custom collection first. Do not synchronize during a controlled cohort unless the protocol calls for changing its retrieval snapshot.

To inspect availability without modifying the corpus, use the application's remediation panel or call `remediation_rag.status()` inside the service.

## If retrieval is unavailable

WARP can retain an evaluated candidate even if the vector service or relevant examples are unavailable. The evidence must show the empty/unavailable retrieval rather than claiming grounded generation. Diagnose connectivity or corpus state before repeating a paid experiment solely to obtain RAG.

The technical boundaries are covered in [Agent runtime](../technical/agent-runtime.md); the retrieval functions are mapped in the [source reference](../reference/source-map.md).
