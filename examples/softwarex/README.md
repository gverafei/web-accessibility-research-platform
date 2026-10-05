# SoftwareX illustrative examples

Portable recorded examples for A11yResearch. This folder is separate from the
private research/manuscript workspace. Preparation does not imply publication.
`MANIFEST.json` records package sizes, SHA-256, counts and source record IDs.

| Example | Package | Contents |
| --- | --- | --- |
| 1 | `example-1-tranco-900.warp` | 900 frozen evaluated pages, historical Tranco list 94XL2 |
| 2 | `example-2-remediations-125.warp` | All 125 minimal-patch runs, 25 sources per popularity stratum; originals, candidates, iterations and events |
| 3 | `example-3-browser-evaluation.warp`, `example-3-browser-remediation.warp` | Newly authorized www.uv.mx demonstration; not the historical 125-page study |
| 4 | `example-4-batch-A.warp`, `example-4-batch-B.warp` | The exact two five-page packages used in the recorded round-trip |
| 4 | `example-4-combined-10.warp` | The combined ten-page evaluation, with recorded measurements and provenance |

Example 2 preserves the original frozen GPT-6 Luna / Light reasoning,
Minimal patches, RAG-ACT off and WAVE off settings. Its historical US$0.15 /
240-second limits are not replaced by current defaults. Timestamps and costs
describe those original executions; importing does not generate new charges.
The extension example is a separate later demonstration; the manuscript does
not report its outcome as part of the controlled 125-page comparison.

## Restore in A11yResearch

1. Use a current installation with remediation exchange support.
2. Open **Import**, choose one `.warp` file and optionally name its records.
3. Evaluation packages open an independent evaluation. Remediation packages
   restore terminal runs with their source observations and execution history.
4. Browse **Remediation runs** to inspect candidates and agentic logs. Imported
   run costs are historical, not new local charges. No model keys are needed
   for import or inspection, and no evaluator/model execution is requested.

Original local IDs in the manifest are provenance; destination IDs differ.
Re-importing creates a separate copy. Comparison-study membership is not bundled;
use **Compare with original** for an accepted restored run. External assets may
have changed, and frozen automated scores do not establish full WCAG conformance.
Missing optional legacy artifacts are documented rather than reconstructed.

## Verify and distribute

Run `python examples/softwarex/verify_packages.py` to check inventory hashes and
counts without extracting or executing HTML. The large bundles are kept out of
normal source commits. Use a versioned release asset or an appropriate data
repository for the actual `.warp` downloads, and add stable links here only after
publication is authorized. No download URLs or DOI are claimed yet.

Before redistribution, review captured third-party HTML, images, prompts and raw
reports for privacy and rights. The software licence does not grant ownership of
captured website content. Do not describe this folder as a clean-room synthetic
dataset or include provider credentials. Never put these packages in the public
documentation site's build.
