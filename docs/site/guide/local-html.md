# Local HTML datasets

Use this workflow to measure files you already possess, including controlled test pages or a reusable research corpus. It is not an import of another investigator's A11yResearch evaluation; that uses the [portable exchange workflow](exchange.md).

## Accepted inputs

Upload individual `.html`/`.htm` files or a ZIP containing HTML and its resources. Ordinary uploads evaluate the HTML files found in the package, without requiring a manifest. Other bundled files are treated as resources.

An example layout is:

```text
corpus.zip
├── index.html
├── pages/
│   └── contact.html
├── css/
│   └── site.css
└── images/
    └── logo.png
```

Use relative paths that still resolve when served from the dataset directory. Bundled assets remain part of the stored dataset. The internal dataset server supplies browser-accessible addresses; the worker does not evaluate an arbitrary host filesystem path.

## Resource policy

The default **isolated** policy restricts loading with a Content Security Policy: external connections and form submissions are blocked, while permitted local/data resources can be rendered. This is useful for reproducibility but can change a page that depends on an external application service.

Choose an external-resource policy only for a trusted dataset when those dependencies are necessary. The policy is stored with the dataset and exported with it. Neither policy establishes that an uploaded page is safe to open outside the controlled environment.

## Validation limits

| Limit | Current value |
| --- | ---: |
| Total uncompressed size | 1,500,000,000 bytes |
| Individual archived file | 100,000,000 bytes |
| Default HTTP upload limit | 3,221,225,472 bytes (3 GiB) |

There is no fixed HTML-observation or archive-file count cap. The importer still rejects unsafe absolute/traversal paths, archive symlinks and oversized datasets. The HTTP upload limit can be changed through `MAX_DATASET_UPLOAD_BYTES`, but raising it does not remove the other byte/path protections. Multipart uploads do not use Flask's default 1,000-part cap. See [resource planning](acquisition.md#collection-size-and-resource-planning) before submitting a large corpus.

## What to inspect

Check that CSS, images and scripts needed for your experiment are bundled and loaded under the chosen policy. Retain the dataset digest and each observation's content digest. If two stored observations are later paired, use explicit identifiers and conditions rather than matching them by their current filename alone.

Remediation creates candidates separately from the stored original. Importing a revised corpus creates new source records with their own content digests.

The implementation is in `dataset_storage.py`; path checks and serving policy are explained in [storage](../technical/storage.md) and [security](../technical/security.md).
