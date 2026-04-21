"""Session history tests: wake-difficulty updates and session/puzzle deletion."""

import unittest

from tests.bootstrap import configure_test_environment, stub_optional_ml_dependencies


configure_test_environment()
stub_optional_ml_dependencies()

from app import app, database as db
from app.models import AlarmSession, Device, PuzzleSession, User


class SessionHistoryRouteTests(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)
        app.config["WTF_CSRF_ENABLED"] = False
        db.drop_all()
        db.create_all()

        self.client = app.test_client()
        self.user = User.register("history@example.com", "password123", "History")
        self.other_user = User.register("other@example.com", "password123", "Other")
        self.device = Device.register("TEST-HISTORY", "Clock", self.user)
        self.other_device = Device.register("TEST-OTHER", "Clock", self.other_user)

        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
            session["_fresh"] = True

    def tearDown(self):
        app.config["WTF_CSRF_ENABLED"] = self.previous_csrf
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_waking_difficulty_saves_valid_score(self):
        """Valid waking difficulty should be saved."""
        alarm_session = AlarmSession.create(
            user_id=self.user.id,
            device_serial=self.device.serial_number,
        )

        response = self.client.post(
            f"/account/session-history/alarm/{alarm_session.id}/waking-difficulty",
            data={"waking_difficulty": "7", "day": "2026-04-20", "tz": "UTC"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(AlarmSession, alarm_session.id).waking_difficulty, 7)

    def test_waking_difficulty_rejects_out_of_range_values(self):
        """Out-of-range waking difficulty should be ignored."""
        alarm_session = AlarmSession.create(
            user_id=self.user.id,
            device_serial=self.device.serial_number,
            waking_difficulty=4,
        )

        response = self.client.post(
            f"/account/session-history/alarm/{alarm_session.id}/waking-difficulty",
            data={"waking_difficulty": "11"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(AlarmSession, alarm_session.id).waking_difficulty, 4)

    def test_delete_alarm_session_removes_child_puzzles(self):
        """Deleting an alarm session should also delete its puzzle rows."""
        alarm_session = AlarmSession.create(
            user_id=self.user.id,
            device_serial=self.device.serial_number,
        )
        PuzzleSession.create(
            alarm_session_id=alarm_session.id,
            puzzle_type="memory",
            question="Repeat pattern",
            is_correct=True,
            time_taken_seconds=10,
        )

        response = self.client.post(
            f"/account/session-history/alarm/{alarm_session.id}/delete",
            data={"day": "2026-04-20", "tz": "UTC"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AlarmSession.query.count(), 0)
        self.assertEqual(PuzzleSession.query.count(), 0)

    def test_delete_puzzle_session_forbidden_for_other_user(self):
        """Users should not be able to delete another user's puzzle row."""
        other_alarm_session = AlarmSession.create(
            user_id=self.other_user.id,
            device_serial=self.other_device.serial_number,
        )
        puzzle_session = PuzzleSession.create(
            alarm_session_id=other_alarm_session.id,
            puzzle_type="maths",
            question="2 + 2",
            is_correct=True,
            time_taken_seconds=4,
        )

        response = self.client.post(
            f"/account/session-history/puzzle/{puzzle_session.id}/delete",
            data={"day": "2026-04-20", "tz": "UTC"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(PuzzleSession, puzzle_session.id))


if __name__ == "__main__":
    unittest.main()
