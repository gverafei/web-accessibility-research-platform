# Concepts and terminology

A11yResearch separates acquiring a page, measuring it and generating a repaired candidate. These are related records, not interchangeable names for the same operation.

| Term | Meaning |
| --- | --- |
| Acquisition | A controlled browser visit or an imported local HTML observation, with retained evidence |
| Evaluation / experiment | A collection of requested observations and their measurements |
| Result | One stored page-level observation within an evaluation |
| Frozen source | The retained HTML used as the immutable starting point for remediation |
| Remediation run | An explicit model/policy configuration applied to one source result |
| Candidate | Generated or patched HTML that is independently measured |
| Iteration | A recorded generation/refinement and its associated measurements and decision |
| Retained candidate | The candidate selected by the deterministic ranking/rollback policy |
| Comparison study | Labeled groups of evaluation results or remediation candidates, including paired originals |
| Composition | A new evaluation assembled from stored results without reevaluating them |
| Provenance | Original record links, evaluation dates and indicators of fresh, cached, imported or composed evidence |

## Three independent research choices

The **model slider** selects a model and, where configured, a reasoning effort. The **intervention slider** selects the permitted type of modification. **Research targets** specify the Axe/Lighthouse thresholds used by the run. Moving one slider is not a substitute for changing another control.

The ordering of the model catalogue is researcher-managed. It is not a benchmark establishing that every position is more capable or more expensive than the preceding one.

## Acquisition is not authenticated tab capture

Live URL acquisition starts a controlled browser visit. The browser extension submits a URL to that workflow; it does not transfer your cookies, session or exact current DOM. A captured source reflects what that visit could load under its bounded acquisition policy.

## Scores, counts and evidence

The primary Axe issue count sums affected-node instances across the selected
WCAG-tagged rules, excluding Best Practices; one node can fail multiple rules.
Best Practices and the combined count remain separate in the raw evidence.
Lighthouse is a 0–100 tool score. Optional WAVE output has its own measurements
and requirements. These tools need not visit exactly the same dynamic state.

Raw reports explain what the summary means. An automated target-reaching candidate is useful experimental evidence, but not proof that all interactions work for every user. Preserve missing values, warnings and pair counts when analyzing results.

## Persistent work

A compact breadcrumb trail above every application screen shows its position
in the workflow. The house icon returns to Dashboard; linked parents return to
the relevant evaluation, remediation list, comparison list or RAG-ACT browser.
Loading and loaded evaluation reports have the same location. Example-detail
navigation preserves search and filters. **RAG-ACT** has its own sidebar entry
for corpus maintenance and browsing, separate from **Configuration**.

Jobs and progress live in MySQL, not only in a browser page. Closing a report does not cancel the underlying work. Pausing an evaluation requests a safe scheduling boundary; an already-running evaluator call can still finish. URL categorization has its own persisted job and stop control.

These distinctions are used throughout the [researcher guides](../guide/acquisition.md) and [technical documentation](../technical/architecture.md).

**Help and documentation**, at the foot of every application screen, opens this
guide in a new tab without replacing an unsaved form. The former About screen
has been removed; old `/about` bookmarks redirect here. Software citation and
attribution are maintained under [License and citation](../reference/citation.md).
