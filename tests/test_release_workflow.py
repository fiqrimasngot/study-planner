import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/release.yaml"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_runs_only_on_main_with_shared_concurrency(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("group: study-planner-release", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("github.repository == 'fiqrimasngot/study-planner'", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertEqual(workflow.count("run: *verify_current_main"), 2)
        for guard, action in [
            ("Verify current main before API publication", "Build and publish API"),
            ("Verify current main before web publication", "Build and publish web"),
            ("Verify current main revision", "Commit and push deployment"),
        ]:
            self.assertLess(workflow.index("- name: " + guard), workflow.index("- name: " + action))

    def test_stale_main_revision_is_rejected(self):
        workflow = WORKFLOW.read_text()
        marker = "      - name: Verify current main before API publication\n"
        self.assertIn(marker, workflow)
        block = workflow.split(marker, 1)[1].split("\n      - name:", 1)[0]
        script = "\n".join(line[10:] for line in block.split("        run: &verify_current_main |\n", 1)[1].splitlines())
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "--allow-empty", "-qm", "initial"], cwd=repo, check=True)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            subprocess.run(["git", "remote", "add", "origin", str(repo)], cwd=repo, check=True)
            for candidate, expected in [(sha, 0), ("a" * 40, 1)]:
                result = subprocess.run(["bash", "-e", "-c", script], cwd=repo,
                                        env={**os.environ, "GITHUB_SHA": candidate}, capture_output=True)
                self.assertEqual(result.returncode, expected, result.stderr.decode())
            # A rerun with its real old SHA must fail after main advances.
            subprocess.run(["git", "checkout", "-qb", "new-main"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "--allow-empty", "-qm", "advance"], cwd=repo, check=True)
            subprocess.run(["git", "branch", "-f", "main", "HEAD"], cwd=repo, check=True)
            subprocess.run(["git", "checkout", "-q", "--detach", sha], cwd=repo, check=True)
            result = subprocess.run(["bash", "-e", "-c", script], cwd=repo,
                                    env={**os.environ, "GITHUB_SHA": sha}, capture_output=True)
            self.assertEqual(result.returncode, 1, result.stderr.decode())

    def test_unchanged_deployment_is_successful_noop(self):
        workflow = WORKFLOW.read_text()
        block = workflow.split("      - name: Commit and push deployment\n", 1)[1]
        block = block.split("\n      - name:", 1)[0]
        script = block.split("        run: |\n", 1)[1]
        script = "\n".join(line[10:] for line in script.splitlines())
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            manifest = repo / "kubernetes/apps/default/study-planner/app/helmrelease.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("unchanged\n")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True)
            before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True)
            result = subprocess.run(["bash", "-e", "-c", script], cwd=repo,
                                    env={**os.environ, "GITHUB_SHA": "a" * 40},
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True)
            self.assertEqual(before, after)

    def test_changed_deployment_is_committed_and_pushed(self):
        workflow = WORKFLOW.read_text()
        block = workflow.split("      - name: Commit and push deployment\n", 1)[1].split("\n      - name:", 1)[0]
        script = "\n".join(line[10:] for line in block.split("        run: |\n", 1)[1].splitlines())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, repo = root / "remote.git", root / "work"
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
            manifest = repo / "kubernetes/apps/default/study-planner/app/helmrelease.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("old\n")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True)
            subprocess.run(["git", "push", "-q", "origin", "main"], cwd=repo, check=True)
            manifest.write_text("new\n")
            result = subprocess.run(["bash", "-e", "-c", script], cwd=repo,
                                    env={**os.environ, "GITHUB_SHA": "a" * 40}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            pushed = subprocess.check_output(["git", "--git-dir", str(remote), "show", "main:kubernetes/apps/default/study-planner/app/helmrelease.yaml"], text=True)
            self.assertEqual(pushed, "new\n")


if __name__ == "__main__":
    unittest.main()
