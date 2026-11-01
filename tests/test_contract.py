from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_required_application_files_exist(self) -> None:
        required = (
            "api/app.py",
            "api/Dockerfile",
            "api/requirements.txt",
            "api/migrations/001_reminders.sql",
            "web/index.html",
            "web/default.conf",
            "web/Dockerfile",
        )
        for relative in required:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_web_proxies_api_to_same_pod(self) -> None:
        nginx = (ROOT / "web/default.conf").read_text()
        self.assertIn("location /api/", nginx)
        self.assertIn("proxy_pass http://127.0.0.1:8081;", nginx)

    def test_frontend_keeps_local_tasks_and_shared_reminders(self) -> None:
        frontend = (ROOT / "web/index.html").read_text()
        self.assertIn("study-planner-tasks", frontend)
        self.assertIn("localStorage.setItem(taskKey", frontend)
        for marker in (
            "loadReminders",
            "editReminder",
            "toggleReminder",
            "deleteReminder",
        ):
            self.assertIn(marker, frontend)

    def test_api_keeps_migration_and_crud_contract(self) -> None:
        api = (ROOT / "api/app.py").read_text()
        migration = (ROOT / "api/migrations/001_reminders.sql").read_text()
        self.assertIn('"/api/healthz"', api)
        self.assertIn("/api/reminders", api)
        self.assertIn("pg_advisory_xact_lock", api)
        self.assertIn("schema_migrations", api)
        self.assertIn("BIGSERIAL PRIMARY KEY", migration)


if __name__ == "__main__":
    unittest.main()
