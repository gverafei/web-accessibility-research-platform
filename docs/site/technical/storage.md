# Database, artifacts and backups

A11yResearch keeps structured research records in MySQL and large evidence files in mounted directories. The schema initialization/migration helpers are in `web/app/database.py`.

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

Paths are an overview; use the database artifact columns as authoritative rather
than guessing a filename from a URL. Version-4 `.warp` exports stream supported
evidence files inside `/results/raw` as binary ZIP members, with size/hash
references instead of embedding their contents in JSON. Local dataset files are
packaged separately; source provenance remains distinct.

RAG-ACT maintenance state and the active-snapshot pointer live in
`/data/act-rag`, while the indexed examples and vectors live in `qdrant_data`.
Preserve both if the exact retrieval snapshot is needed for restoration.

## Immutability and identity

Remediation reads a stored source and writes candidates separately. Source/result IDs and content/configuration digests identify the evidence used. Copied and imported records receive local IDs while retaining source provenance for cross-installation reference.

`normalize_url()` in `web/app/result_portability.py` lowercases the scheme/host, handles default ports, preserves the query and removes fragments/trailing path slashes. The normalized URL supports catalogue matching and reuse; content digests separately identify captured evidence.

## Backup procedure

1. Pause evaluations and stop worker activity at a safe boundary.
2. Take a MySQL backup with your approved database tooling.
3. Preserve `results/`, `data/` and `datasets/` from the same coherent state.
4. Snapshot `qdrant_data` if the exact retrieval corpus must be preserved.
5. Back up `.env`/configuration secrets separately in a private secret store.
6. Record the source revision, image versions and checksums.
7. Test restoration into an isolated installation before relying on the backup.

A consistent MySQL backup and matched artifact directories support installation recovery. Infrastructure-specific database tools or coordinated volume snapshots provide that consistency. Evaluation-level `.warp` exports complement a backup with portable research records.

## Cleanup

Deleting a record through the UI can remove associated artifacts and affect derived comparisons. Exports preserve selected evaluations before cleanup. `docker compose down -v` also removes named persistent volumes, including the database.

Attempt records support recovery and explain acquisition outcomes. The completed-observation cohort and its available artifacts can be selected separately for a dataset release.
