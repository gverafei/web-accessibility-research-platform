# Import, export and composition

A11yResearch supports sharing completed evaluation evidence so collaborators can combine observations without repeating browser acquisition and tool processing.

## Export an evaluation

The exchange extension remains `.warp` after the software was renamed to A11yResearch. The package identifier `warp-experiment` and version `3` are unchanged, so earlier packages remain compatible.

Use the evaluation's download action to obtain a `.warp` file. This is a ZIP package with an `experiment.json` payload using format `warp-experiment`, version `3`. It includes experiment metadata, environments, page-level data and supported artifacts encoded in the payload. Local dataset packages can additionally include bundled dataset files; Tranco metadata is included when present.

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
assert payload["version"] == 3
print(len(payload["results"]))
for entry in payload["results"]:
    row = entry["data"]
    print(row["url"], row.get("axe_violations"), row.get("lighthouse_score"))
```

This reads the package without importing records or executing its HTML. Keep the archive private if the captured content has redistribution/privacy restrictions.

## Import

Open **Import**, select a supported A11yResearch package and submit it. The importer validates metadata, URLs, duplicates and artifacts, restores files to allowed destinations and records import provenance. Local IDs may differ from the source installation; original source links remain provenance, not an instruction to join against the destination's coincidentally equal IDs.

The `.warp` importer expects the package structure created by A11yResearch's export action. A ZIP of HTML files belongs in the local HTML acquisition workflow. Supported legacy payloads are handled by the importer as well.

## Compose a collection

Open **Combine evaluations**, select source results and create a new collection. A11yResearch clones stored results and their available artifacts with source identifiers and composition provenance. It does not perform a fresh visit or add fresh evaluation charges for the copy.

When source evaluations contain the same normalized URL, the selected record determines which capture is included. Stored acquisition dates, settings and provenance help distinguish observations collected under different conditions.

## What this does not export

The evaluation package is not a complete database backup or a round-trip format for every remediation run, comparison study, configuration secret or Qdrant corpus. Back up the installation separately when migrating all state.

Portable exchange reduces repeated computation, but it does not grant rights to redistribute third-party HTML/images. Share only evidence you are authorized to distribute. See [security](../technical/security.md) and [storage](../technical/storage.md).
