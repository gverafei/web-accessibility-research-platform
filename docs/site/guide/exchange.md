# Import, export and composition

WARP supports sharing completed evaluation evidence so collaborators can combine observations without repeating browser acquisition and tool processing.

## Export an evaluation

Use the evaluation's download action to obtain a `.warp` file. This is a ZIP package with an `experiment.json` payload using format `warp-experiment`, version `3`. It includes experiment metadata, environments, page-level data and supported artifacts encoded in the payload. Local dataset packages can additionally include bundled dataset files; Tranco metadata is included when present.

```bash
# Read/export operation; replace 42 with an existing evaluation ID.
curl --fail --output experiment-42.warp \
  http://localhost/experiments/42/json
```

Only files that exist within the allowed artifact root can be encoded. Inspect completeness before sharing. An exported archive is not a promise that unavailable artifacts have been reconstructed.

## Inspect offline

```python
import json
import zipfile

with zipfile.ZipFile("experiment-42.warp") as package:
    payload = json.loads(package.read("experiment.json"))
assert payload["format"] == "warp-experiment"
assert payload["version"] == 3
print(len(payload["results"]))
for entry in payload["results"]:
    row = entry["data"]
    print(row["url"], row.get("axe_violations"), row.get("lighthouse_score"))
```

This reads the package without importing records or executing its HTML. Keep the archive private if the captured content has redistribution/privacy restrictions.

## Import

Open **Import**, select a supported WARP package and submit it. The importer validates metadata, URLs, duplicates and artifacts, restores files to allowed destinations and records import provenance. Local IDs may differ from the source installation; original source links remain provenance, not an instruction to join against the destination's coincidentally equal IDs.

Do not rename an arbitrary ZIP to `.warp` and assume it is supported. Local HTML ingestion is a different workflow. The importer also handles compatible legacy payload forms where implemented, but new exchanges should use the current UI export.

## Compose a collection

Open **Combine evaluations**, select source results and create a new collection. WARP clones stored results and their available artifacts with source identifiers and composition provenance. It does not perform a fresh visit or add fresh evaluation charges for the copy.

If the same normalized URL is represented more than once, inspect how the composition resolves duplicates and choose the correct temporal/experimental observation. Mixing different acquisition policies or dates can be useful, but must not be described as a simultaneous homogeneous crawl.

## What this does not export

The evaluation package is not a complete database backup or a round-trip format for every remediation run, comparison study, configuration secret or Qdrant corpus. Back up the installation separately when migrating all state.

Portable exchange reduces repeated computation, but it does not grant rights to redistribute third-party HTML/images. Share only evidence you are authorized to distribute. See [security](../technical/security.md) and [storage](../technical/storage.md).
