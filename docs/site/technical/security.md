# Security and deployment boundaries

The supplied installation is a local research platform. It lacks a production multi-user authorization boundary and should not be exposed directly to an untrusted network.

## Protect the service ports

The default Compose mappings can listen on all host interfaces. Bind them to loopback or enforce firewall access restrictions. Keep MySQL and the development evaluator private; dataset-server and Qdrant are internal in the supplied Compose files.

The extension endpoints allow cross-origin access for the local browser workflow. That is not authentication. If you need a shared server, first add authentication/authorization, appropriate CSRF/origin controls, HTTPS, rate limits and an ingress policy. A reverse proxy alone does not supply all of these.

## Untrusted web content

Captured HTML and model output are untrusted. The browser/evaluator can reach network locations from the container network. HTTP(S) validation is not a full SSRF defense: restrict access to internal/private infrastructure and cloud metadata endpoints at the network layer when evaluating untrusted URL lists.

Do not mount private directories or secrets into a browser container unnecessarily. Keep browser/runtime dependencies current and use controlled environments for inspecting generated HTML.

## Local dataset controls

The importer rejects path traversal, absolute paths, ZIP symlinks and oversized archives/files. Dataset-server's isolated policy limits external resources and form actions using CSP. An external policy deliberately relaxes some isolation for dependencies.

Neither CSP nor filename validation makes all uploaded active content safe. Review the selected policy and assets before sharing or opening a candidate outside the research environment.

## Model boundaries

An LLM answer cannot alter budgets, expand permitted scope or claim a tool result. Validate JSON operations, selectors, complete HTML and preservation contracts before execution. Typed-tool records identify what actually ran; source-attributed examples must not be presented as official evidence they are not.

Cloud models receive the prompt/context prepared by WARP, which can include captured content and screenshot evidence for supported workflows. Do not submit confidential/personal content unless you are authorized to send it to that provider and understand its data-handling terms.

## Secrets and backups

Keep `.env`, API keys, database dumps and credential-bearing settings private. Do not embed them in README examples or documentation screenshots. The static GitHub Pages site contains documentation only; it does not host the live application, database or research artifacts.

Before publishing the repository, review tracked files and intended history. Before publishing a dataset, review third-party copyrights, personal information and excluded material separately. A software license does not automatically license captured websites.

## Responsible maintenance

Pause/stop work safely before a storage migration. Preserve valid sources and evidence. Avoid volume deletion as a repair technique and avoid duplicate workers as a performance shortcut. Report security issues privately to the maintainer before posting sensitive reproduction data in a public issue.
