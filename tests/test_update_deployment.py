import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import update_deployment
from scripts.update_deployment import update_helmrelease


class DeploymentUpdaterTests(unittest.TestCase):
    def test_updates_api_and_web_refs_without_touching_other_tags(self) -> None:
        source = """controllers:\n  study-planner:\n    containers:\n      api:\n        image:\n          repository: harbor.example/library/study-planner-api\n          tag: old-api@sha256:old\n      web:\n        image:\n          repository: harbor.example/library/study-planner-web\n          tag: old-web@sha256:old\n      initContainers:\n        init-db:\n          image:\n            repository: postgres-init\n            tag: 1@sha256:init\n"""
        result = update_helmrelease(source, "build-abc123", "sha256:api", "sha256:web")
        self.assertIn("tag: build-abc123@sha256:api", result)
        self.assertIn("tag: build-abc123@sha256:web", result)
        self.assertIn("tag: 1@sha256:init", result)

    def test_rejects_missing_web_image(self) -> None:
        with self.assertRaisesRegex(ValueError, "web"):
            update_helmrelease("api:\n  image:\n    tag: old\n", "build-x", "sha256:a", "sha256:w")

    def test_cli_updates_only_the_live_manifest(self) -> None:
        source = """controllers:\n  api:\n    image:\n      repository: api\n      tag: old-api\n  web:\n    image:\n      repository: web\n      tag: old-web\n"""
        with tempfile.TemporaryDirectory() as directory:
            live = Path(directory) / "helmrelease.yaml"
            template = Path(directory) / "helmrelease.yaml.j2"
            live.write_text(source)
            template.write_text(source)
            argv = [
                "update_deployment.py",
                "--file",
                str(live),
                "--tag",
                "build-test",
                "--api-digest",
                "sha256:api",
                "--web-digest",
                "sha256:web",
            ]
            with patch.object(sys, "argv", argv):
                update_deployment.main()
            self.assertIn("build-test@sha256:api", live.read_text())
            self.assertIn("build-test@sha256:web", live.read_text())
            self.assertEqual(source, template.read_text())


if __name__ == "__main__":
    unittest.main()
