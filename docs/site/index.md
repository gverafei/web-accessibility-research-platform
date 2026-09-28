---
title: WARP — web accessibility research, end to end
---

<div class="warp-hero" markdown>
<div class="eyebrow">Web Accessibility Research Platform</div>

# From web pages to reproducible experiments

Acquire and evaluate collections of web pages, repair accessibility barriers with explicit AI controls, and compare the results without assembling a separate pipeline for every study.

[Get started](getting-started/installation.md){ .md-button .md-button--primary }
[Explore the architecture](technical/architecture.md){ .md-button }
</div>

WARP brings browser acquisition, Axe and Lighthouse measurements, optional WAVE evaluation, agentic remediation and portable experiment records into one Docker-based research environment. This documentation explains both how to conduct an experiment and how the implementation works.

<div class="warp-flow" aria-label="Research workflow">
<span>Acquire</span><b aria-hidden="true">→</b><span>Measure</span><b aria-hidden="true">→</b><span>Curate</span><b aria-hidden="true">→</b><span>Remediate</span><b aria-hidden="true">→</b><span>Compare & share</span>
</div>

<div class="warp-card-grid" markdown>
<div class="warp-card" style="--warp-color:#2467b1" markdown>

### Run a study

Start with URLs, a seeded Tranco sample or local HTML. Inspect screenshots, measurements and captured sources in an evaluation report.

[Acquisition guide](guide/acquisition.md) · [Tranco sampling](guide/tranco.md)
</div>
<div class="warp-card" style="--warp-color:#2f9e66" markdown>

### Explore automated repair

Choose a model, reasoning setting and intervention policy. Follow generation, measurement, refinement and rollback in the recorded evidence.

[Remediation guide](guide/remediation.md) · [Models and reasoning](guide/models.md)
</div>
<div class="warp-card" style="--warp-color:#7555b0" markdown>

### Build on the implementation

Understand service boundaries, worker scheduling, typed tools, versioned skills and deterministic candidate selection.

[Agent runtime](technical/agent-runtime.md) · [Development](development/index.md)
</div>
<div class="warp-card" style="--warp-color:#b76a12" markdown>

### Reuse evidence

Compose evaluations and exchange portable experiment packages with collaborators. Keep the original evaluation date and provenance visible.

[Import and export](guide/exchange.md) · [Research datasets](guide/datasets.md)
</div>
</div>

## What you can expect

| Capability | What WARP records |
| --- | --- |
| Collection-level evaluation | Page-level measurements, browser/tool metadata, screenshots and HTML evidence |
| Explicit AI experiments | Chosen model and reasoning, frozen configuration, prompts, usage and recorded charges |
| Bounded agentic repair | Candidate iterations, tool activity, refinement decisions and the retained candidate |
| Paired comparison | Original-to-candidate links, group summaries and per-page changes |
| Collaboration | Exported artifacts, source identifiers and import/composition provenance |

Acquisition and ordinary Axe/Lighthouse evaluation do **not** call an LLM. Models are used for remediation and optional URL categorization. WAVE and cloud models require separately configured services and may incur charges.

## Read this documentation by role

- **First-time user:** [installation](getting-started/installation.md), [first experiment](getting-started/quickstart.md), then [concepts](getting-started/concepts.md).
- **Researcher:** [remediation](guide/remediation.md), [paired comparisons](guide/comparisons.md), and [dataset construction](guide/datasets.md).
- **Developer:** [architecture](technical/architecture.md), [HTTP interfaces](technical/api.md), and [verification](development/testing.md).
- **Administrator:** [settings](technical/settings.md), [storage](technical/storage.md), and [security](technical/security.md).

This site describes the source on the repository's main branch. The editable model catalogue and saved run configurations let researchers adapt experiments to available providers while retaining the settings used for each result.
