"""Verify documented snippets without executing live/network/provider examples."""
from pathlib import Path
import ast
import json
import os
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "site"
FENCES = re.compile(r"^```(\w+)[^\n]*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


def main():
    checked = executed = 0
    for path in sorted(DOCS.rglob("*.md")):
        for language, code in FENCES.findall(path.read_text(encoding="utf-8")):
            name = str(path.relative_to(ROOT))
            if language == "python":
                ast.parse(code, filename=name)
                if code.splitlines()[0].strip() == "# docs-test: offline":
                    env = {**os.environ, "PYTHONPATH": str(ROOT / "web" / "app")}
                    subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                                   env=env, check=True, timeout=20)
                    executed += 1
                checked += 1
            elif language == "json":
                json.loads(code)
                checked += 1
            elif language == "bash":
                subprocess.run(["bash", "-n"], input=code, text=True,
                               check=True, timeout=10)
                for compose in re.findall(r"docker-compose[\w.-]*\.yml", code):
                    if not (ROOT / compose).is_file():
                        raise SystemExit(f"{name}: missing Compose file {compose}")
                checked += 1
    source_map = (DOCS / "reference" / "source-map.md").read_text(encoding="utf-8")
    references = re.findall(r"`((?:web|evaluator|dataset_server|browser_extension)/[^`]+)`", source_map)
    missing = [name for name in references if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit("Missing source references: " + ", ".join(missing))
    print(f"Verified {checked} snippets; executed {executed} offline examples; "
          f"checked {len(references)} source references.")


if __name__ == "__main__":
    main()
