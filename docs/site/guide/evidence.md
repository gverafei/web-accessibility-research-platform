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

A row is not automatically the final retained candidate. Follow the run's selected iteration and rollback decisions. An LLM's statement that a page is repaired is not a substitute for a completed evaluator response.

## Agentic activity log

Events expose the orchestrator's progress, for example acquisition/preparation, diagnosis, planning, generation, evaluator validation, regression rollback, budget stops and completion. Each event has an actor, type, message, timestamp and structured details where relevant.

These actors describe implementation roles. They do not imply independent models make every decision: budgets, transitions, candidate ranking and persistence are deterministic application logic.

## Error and cost evidence

Cloud usage must be recorded before parsing or validating generated output can fail. A malformed paid answer still consumed resources. An incomplete evaluator response retains its error instead of receiving a fabricated score.

If an interruption occurs after a candidate was successfully measured and committed, the run can preserve that candidate with a warning when the applicable policy permits it. A failure before any completed candidate is different.

## Runtime evidence structure

An `agent-runtime-v1` snapshot includes the state, run ID, intervention step, configured budgets, skill-manifest SHA-256, iteration and activated skills, tool contracts, invocation records and transition history. Individual skills carry their ID/version/digest and source references.

These fields make it possible to distinguish a changed model from a changed procedure even if a UI label remains the same. Keep them with your analysis, rather than reporting only the final score.

## Research checklist

Before reporting a cohort, verify the immutable source identifiers/digests, explicit model/reasoning choice, acquisition/tool versions, actual RAG condition, pair denominator, retained-iteration identity and warning status. Summed run durations are processing totals, not necessarily elapsed server wall time.
