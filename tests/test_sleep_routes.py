"""Sleep route tests: imports, replacement of overlapping rows and background training."""

import unittest
from unittest.mock import patch

from tests.bootstrap import configure_test_environment, stub_optional_ml_dependencies


configure_test_environment()
stub_optional_ml_dependencies()

from app import app, database as db
from app.models import SleepSession, SleepStage, User


class _Thread:
    created = []

    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.daemon = daemon
        _Thread.created.append(self)

    def start(self):
        return None

    def run_later(self):
        return self.target(*self.args, **self.kwargs)


class SleepRouteTests(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()
        _Thread.created = []

        self.client = app.test_client()
        self.user = User.register("sleep@example.com", "password123", "Sleep")
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
            session["_fresh"] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_sleep_update_replaces_overlapping_rows_and_excludes_awake_time(self):
        """New sleep imports should replace overlaps and ignore awake time."""
        initial_payload = {
            "sleep_data": [
                {
                    "stage": "HKCategoryValueSleepAnalysisAsleepCore",
                    "start_date": "2026-04-18T23:00:00+0000",
                    "end_date": "2026-04-19T02:00:00+0000",
                    "creation_date": "2026-04-19T02:05:00+0000",
                    "source_name": "Initial Import",
                },
                {
                    "stage": "HKCategoryValueSleepAnalysisAwake",
                    "start_date": "2026-04-19T02:00:00+0000",
                    "end_date": "2026-04-19T02:30:00+0000",
                    "creation_date": "2026-04-19T02:35:00+0000",
                    "source_name": "Initial Import",
                },
            ]
        }
        replacement_payload = {
            "sleep_data": [
                {
                    "stage": "HKCategoryValueSleepAnalysisAsleepDeep",
                    "start_date": "2026-04-18T23:30:00+0000",
                    "end_date": "2026-04-19T01:30:00+0000",
                    "creation_date": "2026-04-19T01:35:00+0000",
                    "source_name": "Replacement Import",
                },
                {
                    "stage": "HKCategoryValueSleepAnalysisAwake",
                    "start_date": "2026-04-19T01:30:00+0000",
                    "end_date": "2026-04-19T02:00:00+0000",
                    "creation_date": "2026-04-19T02:05:00+0000",
                    "source_name": "Replacement Import",
                },
                {
                    "stage": "HKCategoryValueSleepAnalysisAsleepCore",
                    "start_date": "2026-04-19T02:00:00+0000",
                    "end_date": "2026-04-19T05:00:00+0000",
                    "creation_date": "2026-04-19T05:05:00+0000",
                    "source_name": "Replacement Import",
                },
            ]
        }

        with patch("app.routes.Thread", _Thread):
            first_response = self.client.post("/sleep-data/update", json=initial_payload)
            second_response = self.client.post("/sleep-data/update", json=replacement_payload)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(SleepSession.query.count(), 1)
        self.assertEqual(SleepStage.query.count(), 3)

        sleep_session = SleepSession.query.one()
        self.assertEqual(sleep_session.total_duration, 5 * 3600)
        self.assertEqual(sleep_session.start_date.isoformat(), "2026-04-18T23:30:00")
        self.assertEqual(sleep_session.end_date.isoformat(), "2026-04-19T05:00:00")

    def test_sleep_update_imports_valid_records_with_invalid_rows_present(self):
        """Sleep imports should keep valid rows and ignore invalid ones."""
        payload = {
            "sleep_data": [
                {
                    "stage": "HKCategoryValueSleepAnalysisAsleepCore",
                    "start_date": "2026-04-18T23:00:00+0000",
                    "end_date": "2026-04-19T03:00:00+0000",
                    "creation_date": "2026-04-19T03:05:00+0000",
                    "source_name": "Mixed Import",
                },
                {
                    "stage": None,
                    "start_date": "2026-04-19T03:00:00+0000",
                    "end_date": "2026-04-19T04:00:00+0000",
                    "creation_date": "2026-04-19T04:05:00+0000",
                    "source_name": "Mixed Import",
                },
                {
                    "stage": "HKCategoryValueSleepAnalysisAsleepDeep",
                    "start_date": "not-a-date",
                    "end_date": "2026-04-19T07:00:00+0000",
                    "creation_date": "2026-04-19T07:05:00+0000",
                    "source_name": "Mixed Import",
                },
            ]
        }

        with patch("app.routes.Thread", _Thread):
            response = self.client.post("/sleep-data/update", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SleepSession.query.count(), 1)
        self.assertEqual(SleepStage.query.count(), 1)
        self.assertEqual(SleepSession.query.one().total_duration, 4 * 3600)

    def test_sleep_import_thread_uses_captured_user_id(self):
        """The sleep-training thread should use the captured user id."""
        payload = {
            "sleep_data": [
                {
                    "stage": "HKCategoryValueSleepAnalysisAsleepCore",
                    "start_date": "2026-04-18T23:00:00+0000",
                    "end_date": "2026-04-19T03:00:00+0000",
                    "creation_date": "2026-04-19T03:05:00+0000",
                    "source_name": "Unit Test",
                },
                {
                    "stage": "HKCategoryValueSleepAnalysisAsleepDeep",
                    "start_date": "2026-04-19T03:00:00+0000",
                    "end_date": "2026-04-19T07:00:00+0000",
                    "creation_date": "2026-04-19T07:05:00+0000",
                    "source_name": "Unit Test",
                },
            ]
        }

        with patch("app.routes.Thread", _Thread):
            response = self.client.post("/sleep-data/update", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_Thread.created), 1)

        with patch("app.analysis.train_user_model") as train_user_model:
            _Thread.created[0].run_later()

        train_user_model.assert_called_once_with(self.user.id)


if __name__ == "__main__":
    unittest.main()
