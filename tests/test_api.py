from __future__ import annotations

import importlib.util
import json
import threading
import unittest
import urllib.request
from urllib.error import HTTPError
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "api" / "app.py"
SPEC = importlib.util.spec_from_file_location("study_planner_api", MODULE_PATH)
assert SPEC and SPEC.loader
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


class PayloadValidationTests(unittest.TestCase):
    def test_create_defaults_optional_fields_to_null(self) -> None:
        payload = api.validate_payload({"title": "Read chapter 4"}, partial=False)

        self.assertEqual(
            payload,
            {
                "title": "Read chapter 4",
                "details": None,
                "remind_at": None,
            },
        )

    def test_rejects_blank_titles(self) -> None:
        with self.assertRaisesRegex(ValueError, "title must not be blank"):
            api.validate_payload({"title": "   "}, partial=False)

    def test_rejects_invalid_reminder_times(self) -> None:
        with self.assertRaisesRegex(ValueError, "remind_at"):
            api.validate_payload(
                {"title": "Review notes", "remind_at": "2026-10-31T12:00:00"},
                partial=False,
            )

    def test_rejects_empty_patches(self) -> None:
        with self.assertRaisesRegex(ValueError, "patch must not be empty"):
            api.validate_payload({}, partial=True)


class _Rows:
    def fetchall(self):
        now = datetime(2026, 10, 31, tzinfo=timezone.utc)
        return [
            {
                "id": 7,
                "title": "Read chapter 4",
                "details": None,
                "remind_at": None,
                "completed": False,
                "created_at": now,
                "updated_at": now,
            }
        ]


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _query, _params=None):
        return _Rows()


class _MissingConnection(_Connection):
    def execute(self, _query, _params=None):
        return _MissingRows()


class _MissingRows:
    rowcount = 0

    def fetchone(self):
        return None


class ReminderHttpTests(unittest.TestCase):
    def test_list_returns_json_array(self) -> None:
        original_connect = api.connect
        api.connect = _Connection
        server = api.ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/api/reminders"
            ) as response:
                self.assertEqual(response.status, 200)
                payload = json.load(response)
            self.assertIsInstance(payload, list)
            self.assertEqual(payload[0]["id"], "7")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            api.connect = original_connect

    def test_invalid_and_missing_ids_return_not_found(self) -> None:
        original_connect = api.connect
        api.connect = _MissingConnection
        server = api.ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for path in ("/api/reminders/not-an-id", "/api/reminders/", "/api/reminders/999"):
                with self.assertRaises(HTTPError) as raised:
                    urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}{path}")
                self.assertEqual(raised.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            api.connect = original_connect


if __name__ == "__main__":
    unittest.main()
