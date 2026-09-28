# Frequently asked questions

## Does evaluation use an LLM?

No. Ordinary acquisition and Axe/Lighthouse evaluation use browser/testing tools. Remediation and optional URL categorization use the explicitly selected local or cloud model. WAVE is a separately configured optional API.

## Is the highest model slider position always best?

No. The order is an editable research configuration, not a benchmark. Model capability, reasoning, latency and actual charges depend on provider behavior and the task. Evaluate your choices with controlled experiments.

## Will another model be selected if mine fails?

No silent model/provider substitution is permitted. The explicit frozen choice remains the experiment's identity. Diagnose the failure and make a new explicit choice for a new run if needed.

## Do the intervention sliders change the score targets?

No. They change the permitted repair/regeneration scope and its recipe. General settings define shared Axe/Lighthouse targets, frozen for each new run.

## Why does “RAG enabled” not mean RAG used?

Adaptive retrieval waits for measured findings in a later refinement. Relevant complete examples may be unavailable. Inspect actual activation and supplied evidence in the iteration trace.

## Can I close a report or extension panel while it runs?

The backend stores progress and runs independently. Closing the panel does not cancel acquisition or an already-created remediation. Return to the application/panel to inspect status; avoid submitting a duplicate request.

## Can the extension capture my logged-in page exactly?

Not in this build. It submits the URL; WARP performs its own visit without exporting tab cookies/session/live DOM. Authenticated or required interactive states may differ.

## Are processing seconds the time on my clock?

Not necessarily. Recorded/summed tool and run durations differ from elapsed wall time, queue delays, overlapping work and reused observations. Preserve actual accounting instead of inventing interrupted durations.

## Can `.warp` migrate the whole installation?

It exchanges evaluation evidence and supported dataset/artifact metadata. It is not a full database/configuration/remediation/vector-store backup. See [storage](../technical/storage.md).

## Does a sample represent the whole ranking?

That depends on the sampling frame, design, eligibility/nonresponse and estimand. Ordinary report means describe the observed cohort. Population estimates need appropriate weights and uncertainty; no size alone guarantees equivalence.

## Does GitHub Pages run WARP?

No. It hosts this static documentation. Run the Docker application separately. Provider keys, database contents and captures are not uploaded as site assets.

## Where do I ask for help?

Use the repository's issue tracker for a non-sensitive reproducible software issue. Include the source revision, affected workflow, sanitized error and relevant environment/tool versions. Never include keys or confidential page captures.
