# Extending WARP

Extend one boundary at a time and preserve the existing research contracts. An extension should not silently change what an old experiment means.

## Add a model without code changes

Use the researcher-managed [catalogue](../guide/models.md). Discovery/manual provider-qualified identifiers, capabilities, reasoning, order and colors already cover ordinary future model additions. Change provider plumbing only when the request/response protocol actually differs.

A new provider/model family must not become an automatic fallback for a failed selection. Keep explicit choice IDs and frozen snapshots in queued requests and runs.

## Add a typed tool

1. Define a versioned `ToolContract` with required input keys and output type.
2. Register a real handler in the runtime binding layer.
3. Validate the handler's selectors, paths, limits and candidate mutation scope.
4. Persist invocation/version/error evidence.
5. Add contract and failure-path tests.
6. If a skill can use it, update that skill's tool list and version.

See the executable [registry example](../technical/agent-runtime.md). The typed registry checks basic structure; it does not replace domain validation or sandboxing.

## Add or change a runtime skill

Modify `agent_skills/manifest.json`, retaining complete ID/version/stages/steps/tools/instruction/sources fields. Cite primary procedure sources where applicable and distinguish platform-authored guidance. Verify the catalogue computes the new digest and that activated skill evidence appears in iterations.

A runtime procedure changes only when its manifest entry and implementation change. Editing a documentation page does not activate a new procedure in an experiment.

## Add a measurement

Implement a real typed evaluator result, preserve raw evidence and expose missing/failure states. Update database migration helpers, worker persistence, downloads, comparison denominators and portability as needed. Never fill a missing new score with zero to preserve a convenient chart shape.

If the new tool has a paid or external dependency, make that selection explicit and record charges. Keep tool outputs distinct instead of pretending they observe an identical DOM.

## Change acquisition or sampling

Version the policy and sampling-order namespace when changing behavior that affects reproducibility. Preserve pinned frames, source digests and ordered reserves. Do not retroactively mutate old cohorts to match a new selector.

Acquisition and content eligibility must remain separate from accessibility outcomes. Validate changes with fixtures plus a bounded, authorized pilot, especially where replacements or nonresponse are involved.

## Changes needing a migration plan

Database/schema changes, export format changes, new worker concurrency and changed candidate acceptance are not cosmetic updates. Specify backward compatibility, recoverability, evidence versioning and tests before deploying them to an active installation.
