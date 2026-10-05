# Import, export and composition

A11yResearch supports sharing completed evaluation evidence so collaborators can combine observations without repeating browser acquisition and tool processing.

## Export an evaluation

The exchange extension remains `.warp` after the software was renamed to A11yResearch. New exports use package identifier `warp-experiment`, version `4`.

Use the evaluation's download action to obtain a `.warp` ZIP. Its small `experiment.json` manifest contains metadata, environments, page-level data and artifact references with size and SHA-256. Evidence files are binary ZIP members under `artifacts/`, streamed without accumulating their contents in memory. Local datasets can additionally include bundled files under `dataset/`; Tranco metadata is included when present. Update the receiving installation before importing version 4.

```bash
# Read/export operation; replace 42 with an existing evaluation ID.
curl --fail --output experiment-42.warp \
  http://localhost/experiments/42/json
```

The export includes available supported artifacts from the result's artifact directory. Its contents reflect the evidence present in the installation at export time.

Download buttons show a spinner while the server prepares the file. It stops
when the file is handed to the browser for saving, not after you save or cancel
the dialog. This also applies to CSV and raw JSON/HTML evidence downloads.
It does not indicate that all streamed bytes have been written to disk.

## Inspect offline

```python
import json
import zipfile

with zipfile.ZipFile("experiment-42.warp") as package:
    payload = json.loads(package.read("experiment.json"))
assert payload["format"] == "warp-experiment"
assert payload["version"] == 4
print(len(payload["results"]))
for entry in payload["results"]:
    row = entry["data"]
    print(row["url"], row.get("axe_violations"), row.get("lighthouse_score"))
```

This reads the package without importing records or executing its HTML. Keep the archive private if the captured content has redistribution/privacy restrictions.

## Import

Open **Import**, select a supported A11yResearch package and submit it. The importer validates metadata, URLs, duplicates and artifacts, restores files to allowed destinations and records import provenance. Local IDs may differ from the source installation; original source links remain provenance, not an instruction to join against the destination's coincidentally equal IDs.

The `.warp` importer expects the package structure created by A11yResearch's export action and validates binary evidence hashes during extraction. A ZIP of HTML files belongs in the local HTML acquisition workflow. Upload and uncompressed-storage limits still apply; this exchange format is not an unrestricted backup mechanism.

The default HTTP upload budget is 3 GiB and can be changed with
`MAX_DATASET_UPLOAD_BYTES`. Version-4 packages additionally limit the manifest
to 64 MiB, non-directory members to 100,001 and referenced evidence to 32 GiB
uncompressed. Bundled local datasets retain their separate 1.5-billion-byte total
and 100-million-byte file limits. A large export can therefore need a higher
receiving upload budget even though export streams its evidence successfully.

## Export and import remediations

**Download CSV** in a remediation report exports its original and recorded
iterations for analysis, without generating or evaluating anything. It is not an
importable package; use **Export data** for complete portable evidence.

Open a terminal remediation report or its history row and choose **Export data**.
For a batch, click a record's non-interactive area or select the checkbox beside its
page name directly in **Remediation runs**. The entire selected record stays highlighted
in table and card views; links and action buttons retain their normal behavior. Then
choose **Export selected**, the first control before Table/Cards and search. The button
shows the selected count and downloads one `.warp` package. Search by URL, name,
ID or status; **Select all** beside the toolbar checkbox selects only visible completed runs. Selections
remain selected when you change the filter or switch between table and cards,
including selected rows hidden by a filter. Active runs cannot be selected or exported.
Keyboard users can select the native checkboxes with Space.

When the package contains multiple runs, its suggested filename includes the export
date and time in the configured application timezone, for example
`remediations-20261005-090703.warp` (compact date and time separated by a hyphen).
Single-run exports keep `remediation-<ID>.warp`.

These packages use `warp-remediations`, version `1`, with `remediation.json`.
They contain the linked frozen source observations and recorded environments,
run configuration, templates used, all stored iterations and events, candidate
HTML, screenshots, raw evaluator files and model-call/response evidence when
available. Binary files retain their bytes and carry size/SHA-256 references.
Missing optional legacy artifacts are listed, never reconstructed. A referenced
candidate or original rendered HTML must be present for export to succeed.

Use the same **Import** page for either package type. Remediation imports create
new source evaluations and runs, remap their source/retained-iteration/file links,
and retain terminal status, measurements, timestamps, decisions and historical
costs. They do **not** queue a job, call a model/evaluator, or publish a candidate.
The restored source evaluations contain only the observations linked to the
selected runs, not necessarily the entire original collection. Retained sampling
metadata describes the original acquisition; it does not establish that the
exported subset is a new representative sample. Export the full source evaluation
separately when that collection is needed for study-wide analysis.
Run reports mark imported evidence; historical imported costs are excluded from
the Dashboard and remediation-history local cost total. Re-export preserves
prior import provenance. Re-importing creates another independent copy.

Validation checks references, terminal states, duplicate paths, traversal,
symlinks, sizes and all binary hashes before records are created. The same
64-MiB manifest, 100,001-member and 32-GiB evidence limits apply. Database writes
are transactional; failure removes only that import's new artifact directories.
The receiving HTTP upload limit still applies.

```bash
# Export existing recorded evidence; no new remediation is submitted.
curl --fail --output remediation-21.warp http://localhost/remediation/21/export
# Export a selected batch of terminal runs.
curl --fail --output remediations.warp \
  --data 'run_ids=21&run_ids=22' http://localhost/remediation/export
```

Inspect `remediation.json` offline with a ZIP reader before sharing. Prompts and
captured pages can contain sensitive material even though provider settings and
credentials are not exported. Historical prompts, event details and checkpoint
files preserve their original identifiers/paths as provenance; only live file
links in the imported records are relocated. This is evidence transfer, not a
guarantee that external assets remain available or that live interactions replay.
Original local-dataset resource bundles and browser sessions are not included in
a remediation package; export the source dataset evaluation separately if needed.

## Compose a collection

Open **Combine evaluations**, select source results and create a new collection. A11yResearch clones stored results and their available artifacts with source identifiers and composition provenance. It does not perform a fresh visit or add fresh evaluation charges for the copy.

The destination and source selectors share aligned headers at the top of their
panels. Page counts, matching search/selection controls and the two lists also
align. Secondary actions sit in the panel footers. Click **Page** in the source
list to alternate ascending and descending URL order. Panels grow with their
content up to the available screen space, then scroll internally; on narrow
screens they stack vertically.

**Available pages** counts selectable source observations under the current
filter; pages already in the destination remain visible but disabled and marked
**Already present**.

Each normalized URL appears only once in the destination. Existing observations
are never automatically replaced, including through the composition API. To use
a different observation of the same URL, first explicitly remove it from the
left-hand destination list, then add the desired source observation. Removal
deletes the destination's copy and its generated files, not the source record.
Stored acquisition dates, settings and provenance help distinguish observations
collected under different conditions.

For example, two collaborators can contribute disjoint batches without
remeasuring their pages:

| Step | Input | Result |
| --- | --- | --- |
| Export and import A | Five stored pages | Five restored observations and available evidence |
| Export and import B | Five different stored pages | A second five-page batch |
| Combine A and B | Both imported batches | Ten observations with measurements and source provenance retained |

This illustrates the workflow, not a guaranteed package size or evidence of
transfer between different machines. Exporting, importing and combining stored
results do not initiate browser acquisition or evaluator calls.

## What this does not export

Neither package type is a complete database backup. Comparison-study membership,
browser-extension delivery requests/sessions, configuration secrets and the
Qdrant corpus are not transferred. Remediation packages restore recorded terminal
runs, not resumable active jobs. Back up the installation separately when
migrating all state.

Portable exchange reduces repeated computation, but it does not grant rights to redistribute third-party HTML/images. Share only evidence you are authorized to distribute. See [security](../technical/security.md) and [storage](../technical/storage.md).
