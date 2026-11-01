import unittest

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


if __name__ == "__main__":
    unittest.main()
