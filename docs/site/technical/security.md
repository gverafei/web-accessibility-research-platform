# Security and deployment boundaries

The supplied installation is a local research platform. It lacks a production multi-user authorization boundary and should not be exposed directly to an untrusted network.

## Protect the service ports

The default Compose mappings can listen on all host interfaces. Bind them to loopback or enforce firewall access restrictions. Keep MySQL and the development evaluator private; dataset-server and Qdrant are internal in the supplied Compose files.

The extension endpoints allow cross-origin access for the local browser workflow. That is not authentication. If you need a shared server, first add authentication/authorization, appropriate CSRF/origin controls, HTTPS, rate limits and an ingress policy. A reverse proxy alone does not supply all of these.

## Untrusted web content

Captured HTML and model output are untrusted. The browser/evaluator can reach network locations from the container network. HTTP(S) validation is not a full SSRF defense: restrict access to internal/private infrastructure and cloud metadata endpoints at the network layer when evaluating untrusted URL lists.

Browser containers benefit from minimal filesystem mounts and current runtime dependencies. Controlled inspection environments isolate generated HTML from private files and credentials.

## Local dataset controls

The importer rejects path traversal, absolute paths, ZIP symlinks and oversized archives/files. Dataset-server's isolated policy limits external resources and form actions using CSP. An external policy deliberately relaxes some isolation for dependencies.

Neither CSP nor filename validation makes all uploaded active content safe. Review the selected policy and assets before sharing or opening a candidate outside the research environment.

## Model boundaries

Before applying generated changes, A11yResearch validates JSON operations, selectors, complete HTML and preservation requirements. Run settings determine budgets and change scope. Tool records and source links identify the measurements and retrieved examples used during processing.

Cloud prompts can contain captured page content and, for supported workflows, screenshot evidence. Provider data-handling terms and authorization to share that content are relevant when choosing local or cloud processing.

## Secrets and backups

`.env`, API keys, database dumps and credential-bearing settings belong in private storage. The static GitHub Pages site serves documentation; the application, database and captured evidence run in the researcher's installation.

Captured websites retain their own copyright and privacy conditions, separately from the software license. These conditions affect which artifacts can be shared in a dataset release.

## Responsible maintenance

Backups and a scheduling pause protect active research state during storage maintenance. Removing Docker volumes deletes persistent data. Security issues involving sensitive reproduction data can be reported privately to the maintainer.
