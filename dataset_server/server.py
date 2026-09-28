import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DATASET_ROOT = Path("/datasets").resolve()
ISOLATED_CSP = (
    "default-src 'self' data: blob:; "
    "script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; "
    "media-src 'self' data: blob:; connect-src 'self'; "
    "frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'"
)


class DatasetHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DATASET_ROOT), **kwargs)

    def end_headers(self):
        parts = [part for part in self.path.split("?", 1)[0].split("/") if part]
        policy = "isolated"
        if parts:
            metadata = DATASET_ROOT / parts[0] / ".warp-dataset.json"
            try:
                policy = json.loads(metadata.read_text(encoding="utf-8")).get(
                    "resource_policy", "isolated"
                )
            except (OSError, ValueError, TypeError):
                pass
        if policy == "isolated":
            self.send_header("Content-Security-Policy", ISOLATED_CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, _format, *_args):
        return


ThreadingHTTPServer(("0.0.0.0", 8080), DatasetHandler).serve_forever()
