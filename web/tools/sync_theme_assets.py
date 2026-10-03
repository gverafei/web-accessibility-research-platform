"""Mirror the shared component skin into the packaged browser extension."""
from pathlib import Path


def sync(root: Path) -> None:
    source = root / "web/app/static/css/theme.css"
    target = root / "browser_extension/theme.css"
    target.write_bytes(source.read_bytes())


if __name__ == "__main__":
    sync(Path(__file__).resolve().parents[2])
