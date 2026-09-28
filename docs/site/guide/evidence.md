# Iteration trace and agentic activity log

The remediation report keeps two complementary records. The iteration trace explains what happened to each candidate. The activity log explains how the orchestration reached those decisions.

## Iteration trace

Inspect an iteration for:

- Its prompt/feedback and generation configuration.
- The candidate HTML and screenshot, when successfully produced.
- Axe/Lighthouse measurements and tool metadata.
- Tokens, recorded model charges and processing seconds.
- DOM divergence, content retention and visual evidence.
- Applied/skipped patch operations and preservation warnings.
- Retrieved ACT sources and actual context supplied.
- The decision to accept, retain, refine or roll back.
- Activated skill IDs, versions/digests and typed tool activity.

The run identifies its retained iteration, which can differ from the last generated candidate after a rollback. Its recorded Axe and Lighthouse measurements support the acceptance decision.

## Agentic activity log

Events expose the orchestrator's progress, for example acquisition/preparation, diagnosis, planning, generation, evaluator validation, regression rollback, budget stops and completion. Each event has an actor, type, message, timestamp and structured details where relevant.

Actors identify orchestration roles. The application manages budgets, state transitions, candidate ranking and persistence, while models perform the configured diagnosis and generation tasks.

## Error and cost evidence

Usage records include cloud responses that later fail output validation, so their tokens and charges remain visible in the run totals. Incomplete evaluator responses include their error details and identify the unavailable measurements.

If an interruption occurs after a candidate was successfully measured and committed, the run can preserve that candidate with a warning when the applicable policy permits it. A failure before any completed candidate is different.

## Runtime evidence structure

An `agent-runtime-v1` snapshot includes the state, run ID, intervention step, configured budgets, skill-manifest SHA-256, iteration and activated skills, tool contracts, invocation records and transition history. Individual skills carry their ID/version/digest and source references.

These fields help researchers distinguish changes in the model, procedure and experimental settings when comparing results.

## Research checklist

Before reporting a cohort, verify the immutable source identifiers/digests, explicit model/reasoning choice, acquisition/tool versions, actual RAG condition, pair denominator, retained-iteration identity and warning status. Summed run durations are processing totals, not necessarily elapsed server wall time.
