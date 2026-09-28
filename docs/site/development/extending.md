# Extending WARP

WARP exposes extension points for models, tools, remediation procedures, measurements and sampling designs. Versioned configuration and evidence connect these components to the experiments that use them.

## Add a model without code changes

Use the researcher-managed [catalogue](../guide/models.md). Discovery/manual provider-qualified identifiers, capabilities, reasoning, order and colors already cover ordinary future model additions. Change provider plumbing only when the request/response protocol actually differs.

Provider integrations use the selected choice ID and its frozen configuration in queued requests and runs.

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

A new measurement integrates with evaluator responses, raw evidence storage, database migrations, worker persistence, downloads, comparisons and portable exports. Its response includes availability and failure status as well as the measured value.

Paid or external tools need a configuration choice and usage accounting. Separate tool records preserve each tool's execution and page-state context.

## Change acquisition or sampling

Acquisition policies and sampling-order namespaces are versioned alongside pinned frames, source digests and ordered reserves. Existing cohorts retain their original selector and recovery history.

Sampling tests cover allocation, deterministic ordering, replacements and nonresponse. A live-page pilot can check acquisition behavior for a new policy or source.

## Changes needing a migration plan

Database/schema changes, export format changes, new worker concurrency and changed candidate acceptance are not cosmetic updates. Specify backward compatibility, recoverability, evidence versioning and tests before deploying them to an active installation.
