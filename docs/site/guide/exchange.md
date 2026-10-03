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

## Compose a collection

Open **Combine evaluations**, select source results and create a new collection. A11yResearch clones stored results and their available artifacts with source identifiers and composition provenance. It does not perform a fresh visit or add fresh evaluation charges for the copy.

When source evaluations contain the same normalized URL, the selected record determines which capture is included. Stored acquisition dates, settings and provenance help distinguish observations collected under different conditions.

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

The evaluation package is not a complete database backup or a round-trip format for every remediation run, comparison study, configuration secret or Qdrant corpus. Back up the installation separately when migrating all state.

Portable exchange reduces repeated computation, but it does not grant rights to redistribute third-party HTML/images. Share only evidence you are authorized to distribute. See [security](../technical/security.md) and [storage](../technical/storage.md).
