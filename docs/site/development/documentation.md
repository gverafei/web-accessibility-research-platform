# Maintaining this documentation

The site uses Material for MkDocs and publishes from the same Git repository as WARP. Its source is plain Markdown in `docs/site`; the sidebar and build configuration are in root `mkdocs.yml`.

## Preview locally

```bash
python3 -m venv .venv-docs
source .venv-docs/bin/activate
python -m pip install -r requirements-docs.txt
mkdocs serve --dev-addr 127.0.0.1:8001
```

Open `http://127.0.0.1:8001/web-accessibility-research-platform/`. The project prefix matches the GitHub Pages URL. This is the static documentation preview, not the application. It does not run acquisitions, import private results or require MySQL.

## Add a page

1. Add a Markdown file to the appropriate guide/technical/reference directory.
2. Add it to `nav` in `mkdocs.yml`.
3. Link related concepts with relative `.md` paths.
4. Add the relevant source files and full service URLs to technical references.
5. Run the example/build/link checks and visually inspect the result.

Keep credentials, captured pages and generated experiment outputs outside `docs/site`. Only this directory becomes public site content.

## Examples

Mark a Python fence's first line `# docs-test: offline` only if it is safe and self-contained without network, a database, filesystem mutation or paid operations. The checker executes that marked example in a subprocess with the source modules on `PYTHONPATH`.

Unmarked Python examples are syntax-checked, not executed. JSON fences are parsed. Bash fences are checked with `bash -n`, not run. Label state-changing/provider operations clearly in the surrounding text.

## Build and verify

```bash
python docs/tools/check_examples.py
mkdocs build --strict
python docs/tools/check_site.py
git diff --check
```

`site/` contains generated output and is ignored by Git. The workflow uploads it as a Pages artifact; Markdown and configuration remain the editable source.

## GitHub Pages setup

The repository administrator selects **Settings → Pages → Source: GitHub Actions** once. `.github/workflows/documentation.yml` validates pull requests and builds/deploys pushes to `main`. A manual workflow dispatch can rebuild the current source.

Deployment uses the `github-pages` environment with Pages/id-token permissions. It does not require an OpenRouter key, application secret or database credential. If Pages is not enabled, a successful local build alone does not establish that the public site is live.

The canonical URL is `https://gverafei.github.io/web-accessibility-research-platform/`. Update `site_url` and README links together if the repository/owner or custom domain changes.

The source repository is private. Publishing Pages from a private repository requires a compatible GitHub plan; the documentation website itself remains public. Repository privacy is not a substitute for reviewing the generated site for confidential information.

## Scope and versions

The main-branch site describes the current software. A pinned revision or release connects an experiment to the corresponding source. Maintained versions can have separate documentation when their workflows differ.
