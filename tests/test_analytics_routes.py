"""Analytics route tests: recommendation output and charts."""

import unittest
from datetime import timedelta
from unittest.mock import patch

from tests.bootstrap import configure_test_environment, stub_optional_ml_dependencies


configure_test_environment()
stub_optional_ml_dependencies()

from app import app, database as db
from app.models import AlarmSession, Device, PuzzleSession, User
from app.utils import utc_now


class AnalyticsRouteTests(unittest.TestCase):
    def setUp(self):
        """Set up test context, create test user/device and ensure a clean database."""
        self.app_context = app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()

        self.client = app.test_client()
        self.user = User.register("analytics@example.com", "password123", "Analytics")
        self.device = Device.register("TEST-ANALYTICS", "Clock", self.user)

        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
            session["_fresh"] = True

    def tearDown(self):
        """Clean up database and pop app context."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_recommendation_returns_time_and_best_puzzle_type(self):
        """Test that the recommendation endpoint returns a valid time and best puzzle type based on past sessions."""
        session_one = AlarmSession.create(
            user_id=self.user.id,
            device_serial=self.device.serial_number,
            triggered_at=utc_now() - timedelta(days=2),
        )
        PuzzleSession.create(
            alarm_session_id=session_one.id,
            puzzle_type="maths",
            question="2 + 2",
            is_correct=True,
            time_taken_seconds=5,
            outcome_action="dismissed",
        )

        session_two = AlarmSession.create(
            user_id=self.user.id,
            device_serial=self.device.serial_number,
            triggered_at=utc_now() - timedelta(days=1),
        )
        PuzzleSession.create(
            alarm_session_id=session_two.id,
            puzzle_type="memory",
            question="Repeat pattern",
            is_correct=False,
            time_taken_seconds=12,
            outcome_action="snoozed",
        )

        candidate_time = utc_now().replace(hour=7, minute=15, second=0, microsecond=0)
        with patch("app.routes.should_retrain_model", return_value=False), patch(
            "app.routes.find_suitable_alarm",
            return_value={"best_candidate": {"candidate_time": candidate_time}},
        ):
            response = self.client.get("/api/analytics/recommendation")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"time": "07:15", "best_puzzle_type": "maths"})

    def test_analytics_aggregates_sessions(self):
        """Test that the analytics endpoints return aggregated data based on past sessions."""
        session_a = AlarmSession.create(
            user_id=self.user.id,
            device_serial=self.device.serial_number,
            triggered_at=utc_now() - timedelta(days=8),
        )
        PuzzleSession.create(
            alarm_session_id=session_a.id,
            puzzle_type="maths",
            question="3 + 3",
            is_correct=True,
            time_taken_seconds=6,
            outcome_action="dismissed",
        )

        session_b = AlarmSession.create(
            user_id=self.user.id,
            device_serial=self.device.serial_number,
            triggered_at=utc_now() - timedelta(days=7),
        )
        PuzzleSession.create(
            alarm_session_id=session_b.id,
            puzzle_type="memory",
            question="Repeat pattern",
            is_correct=True,
            time_taken_seconds=11,
            outcome_action="snoozed",
        )
        PuzzleSession.create(
            alarm_session_id=session_b.id,
            puzzle_type="memory",
            question="Repeat pattern again",
            is_correct=True,
            time_taken_seconds=7,
            outcome_action="dismissed",
        )

        session_c = AlarmSession.create(
            user_id=self.user.id,
            device_serial=self.device.serial_number,
            triggered_at=utc_now() - timedelta(days=1),
        )
        PuzzleSession.create(
            alarm_session_id=session_c.id,
            puzzle_type="memory",
            question="Repeat pattern",
            is_correct=False,
            time_taken_seconds=8,
            outcome_action="snoozed",
        )

        success_over_time_response = self.client.get("/api/analytics/success-over-time")
        alarm_success_response = self.client.get("/api/analytics/alarm-success")
        puzzle_types_response = self.client.get("/api/analytics/puzzle-types")

        self.assertEqual(success_over_time_response.status_code, 200)
        self.assertEqual(alarm_success_response.status_code, 200)
        self.assertEqual(puzzle_types_response.status_code, 200)

        success_payload = success_over_time_response.get_json()
        self.assertEqual(len(success_payload["labels"]), len(success_payload["values"]))
        self.assertEqual(sum(success_payload["values"]), 3)

        self.assertEqual(
            alarm_success_response.get_json(),
            {"labels": ["Successful", "Unsuccessful"], "values": [66.66666666666666, 33.33333333333333]},
        )

        self.assertEqual(
            puzzle_types_response.get_json(),
            {"labels": ["maths", "memory"], "values": [100.0, 66.67]},
        )


if __name__ == "__main__":
    unittest.main()
