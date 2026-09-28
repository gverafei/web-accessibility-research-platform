"""Check generated local HTML targets/anchors and searchable document coverage."""
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
PROJECT_PREFIX = "/web-accessibility-research-platform/"


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.links = []
        self.ids = set()
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag in {"img", "script"} and values.get("src"):
            self.links.append(values["src"])
        if tag == "link" and values.get("href") and "stylesheet" in values.get("rel", "").split():
            self.links.append(values["href"])


def main():
    pages = {path.resolve(): Page(path) for path in SITE.rglob("*.html")}
    if not pages:
        raise SystemExit("No built HTML; run mkdocs build --strict first.")
    failures = []
    links = 0
    for source, page in pages.items():
        for href in page.links:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc:
                continue
            links += 1
            address = unquote(parsed.path)
            if address.startswith(PROJECT_PREFIX):
                target = SITE / address[len(PROJECT_PREFIX):]
            elif address.startswith("/"):
                failures.append(f"{source.relative_to(SITE)}: unexpected absolute URL {href}")
                continue
            else:
                target = source.parent / address if address else source
            if target.is_dir():
                target /= "index.html"
            target = target.resolve()
            if not target.is_relative_to(SITE.resolve()) or not target.exists():
                failures.append(f"{source.relative_to(SITE)}: missing target {href}")
            elif parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target].ids:
                failures.append(f"{source.relative_to(SITE)}: missing anchor {href}")
    index = json.loads((SITE / "search" / "search_index.json").read_text(encoding="utf-8"))
    docs = index.get("docs", [])
    coverage = {entry["location"].split("#", 1)[0] for entry in docs}
    markdown_count = len(list((ROOT / "docs" / "site").rglob("*.md")))
    if len(coverage) < markdown_count:
        failures.append(f"Search covers {len(coverage)} pages, expected at least {markdown_count}.")
    if not any("remediation" in entry.get("text", "").lower() for entry in docs):
        failures.append("Search lacks remediation content.")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Verified {len(pages)} HTML pages, {links} local links/assets and "
          f"{len(coverage)} searchable pages.")


if __name__ == "__main__":
    main()
