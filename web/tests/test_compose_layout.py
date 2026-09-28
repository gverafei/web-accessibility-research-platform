"""Source-level deployment contracts; Compose validates the complete YAML."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ComposeLayoutTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    def service(self, name):
        match = re.search(
            rf"^  {re.escape(name)}:\n(.*?)(?=^  \S|^\S|\Z)",
            self.text, re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match, name)
        return match.group(1)

    def test_application_services_build_from_local_source(self):
        for service, context in (
            ("web", "web"), ("worker", "web"),
            ("evaluator", "evaluator"), ("dataset-server", "dataset_server"),
        ):
            with self.subTest(service=service):
                block = self.service(service)
                self.assertIn(f"    build:\n      context: ./{context}\n", block)
                self.assertNotRegex(block, r"(?m)^    image:")
                self.assertTrue((ROOT / context / "Dockerfile").is_file())

    def test_only_one_compose_file_is_distributed(self):
        self.assertFalse((ROOT / "docker-compose-dev.yml").exists())

    def test_worker_and_browser_supervision_are_preserved(self):
        self.assertIn('command: ["python", "worker.py"]', self.service("worker"))
        self.assertIn("    init: true\n", self.service("evaluator"))
        for service in ("web", "worker"):
            self.assertIn("      - ./web/app:/app\n", self.service(service))

    def test_official_dependencies_and_persistent_storage_are_preserved(self):
        self.assertIn("    image: mysql:8.0\n", self.service("db"))
        self.assertIn("    image: qdrant/qdrant:", self.service("qdrant"))
        self.assertIn("      - mysql_data:/var/lib/mysql\n", self.service("db"))
        self.assertIn("      - qdrant_data:/qdrant/storage\n", self.service("qdrant"))
        self.assertIn("      - ./datasets:/datasets:ro\n", self.service("dataset-server"))


if __name__ == "__main__":
    unittest.main()
