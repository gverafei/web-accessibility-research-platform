# Database, artifacts and backups

WARP keeps structured research records in MySQL and large evidence files in mounted directories. The schema initialization/migration helpers are in `web/app/database.py`.

## Core entities

| Table | Purpose / key relation |
| --- | --- |
| `app_settings` | Persisted general settings and model catalogue |
| `experiments` | Requested URLs, evaluation controls, status and provenance context |
| `experiment_results` | Page measurements, artifact paths, source links and categories |
| `experiment_environment` | Actual environment/tool metadata for evaluations |
| `tranco_samples` | Pinned frame and candidate/reserve metadata |
| `tranco_attempts` | Acquisition-attempt/recovery evidence distinct from valid observations |
| `datasets`, `dataset_observations` | Local corpus identity and individual content digests |
| `remediation_runs` | Immutable-source link, frozen model/targets and execution policy |
| `remediation_iterations` | Generated candidate, measurements, usage and decisions |
| `remediation_events` | Agentic activity log |
| `browser_remediation_requests` | Extension request and linked acquisition/remediation progress |
| `comparison_studies`, `comparison_members` | Grouped source/candidate studies |
| `url_category_jobs` | Persistent categorization job and usage |

Schema compatibility fields and historical tables may remain for reading existing records. Their presence is not a declaration that an old workflow is a current researcher-facing feature. Use the current route/UI contract.

## Artifact locations

```text
/results/raw/
└── experiment_<id>/
    ├── ..._axe.json
    ├── ..._lighthouse.json
    ├── ..._source.html
    ├── ..._response.html       (when available)
    └── screenshots / optional tool artifacts

/datasets/
├── <stored-dataset-key>/      (uploaded HTML and resources)
└── remediations/              (separate generated candidates)
```

Paths are an overview; use the database artifact columns as authoritative rather than guessing a filename from a URL. Result portability only copies/encodes supported files inside `/results/raw` and preserves separate source provenance.

## Immutability and identity

Remediation reads a stored source and writes candidates separately. Source/result IDs and content/configuration digests identify which evidence was used. A copied/imported record has a new local ID, so do not assume IDs from two installations refer to the same page.

`normalize_url()` lowercases the scheme/host, handles default ports, preserves the query and removes fragments/trailing path slashes as implemented. Normalized identity is useful for catalogue/reuse, but it is not a cryptographic content identity.

## Backup procedure

1. Pause evaluations and stop worker activity at a safe boundary.
2. Take a MySQL backup with your approved database tooling.
3. Preserve `results/`, `data/` and `datasets/` from the same coherent state.
4. Snapshot `qdrant_data` if the exact retrieval corpus must be preserved.
5. Back up `.env`/configuration secrets separately in a private secret store.
6. Record the source revision, image versions and checksums.
7. Test restoration into an isolated installation before relying on the backup.

Database tools and volume snapshots depend on your infrastructure; do not copy a live MySQL data directory and assume it is a consistent logical backup. A `.warp` file is an evaluation exchange package, not a complete installation backup.

## Cleanup

Deleting a record through the UI can remove associated artifacts and invalidate derived comparisons. Export what you need first. Never use broad filesystem deletion or `docker compose down -v` to troubleshoot a temporary browser/provider error.

Failed attempts can be useful recovery/audit evidence, but are not valid released observations. Keep internal provenance distinct from the final distributable dataset and avoid indefinitely retaining bulky unusable artifacts without a declared need.
