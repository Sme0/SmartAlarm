"""Model tests: account/device helpers plus puzzle randomizer behavior."""

import unittest
from datetime import time, timedelta
from unittest.mock import patch

from tests.bootstrap import configure_test_environment, stub_optional_ml_dependencies


configure_test_environment()
stub_optional_ml_dependencies()

from app import app, database as db
from app.models import Alarm, AlarmSession, Device, PuzzleSession, User, resolve_effective_puzzle_type
from app.utils import as_utc, utc_now


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_user_register_rejects_duplicate_email_and_verifies_password(self):
        """Users should verify passwords and reject duplicate emails."""
        user = User.register("user@example.com", "password123", "User")

        self.assertTrue(user.verify_password("password123"))
        self.assertFalse(user.verify_password("wrong-password"))

        with self.assertRaises(ValueError):
            User.register("USER@example.com", "password123", "Other")

    def test_generate_pairing_code_sets_code_and_expiry(self):
        """Generating a pairing code should save the code and expiry."""
        device = Device.register("PAIRING-1", "Clock", None)

        with patch("app.models.random.choices", return_value=list("ABC123")):
            code, expiry = device.generate_pairing_code()

        self.assertEqual(code, "ABC123")
        self.assertEqual(device.pairing_code, "ABC123")
        self.assertIsNotNone(expiry)
        self.assertGreater(as_utc(expiry), utc_now())

    def test_device_is_online_uses_recent_heartbeat(self):
        """Online status should depend on a recent heartbeat."""
        user = User.register("online@example.com", "password123", "Online")
        device = Device.register("ONLINE-1", "Clock", user)

        self.assertFalse(device.is_online())

        device.last_seen = utc_now() - timedelta(minutes=1)
        db.session.commit()
        self.assertTrue(device.is_online())

        device.last_seen = utc_now() - timedelta(minutes=3)
        db.session.commit()
        self.assertFalse(device.is_online())

    def test_get_alarms_by_day_groups_valid_days_and_falls_back_invalid_ones(self):
        """Alarm grouping should use the weekday or fall back to Monday for bad values."""
        user = User.register("days@example.com", "password123", "Days")
        device = Device.register("DAYS-1", "Clock", user)

        Alarm.create(device_serial=device.serial_number, user_id=user.id, time=time(7, 0), day_of_week=0, enabled=True, puzzle_type="maths")
        Alarm.create(device_serial=device.serial_number, user_id=user.id, time=time(8, 0), day_of_week=3, enabled=True, puzzle_type="memory")
        bad_alarm = Alarm.create(device_serial=device.serial_number, user_id=user.id, time=time(9, 0), day_of_week=2, enabled=True, puzzle_type="recommended")
        bad_alarm.day_of_week = "bad"
        db.session.commit()

        grouped = device.get_alarms_by_day()

        self.assertEqual(len(grouped["Monday"]), 2)
        self.assertEqual(len(grouped["Thursday"]), 1)

    def test_puzzle_session_create_normalizes_supported_outcomes(self):
        """Puzzle outcomes should be normalized to the supported values."""
        user = User.register("puzzle@example.com", "password123", "Puzzle")
        device = Device.register("PUZZLE-1", "Clock", user)
        Alarm.create(
            device_serial=device.serial_number,
            user_id=user.id,
            time=time(7, 0),
            day_of_week=1,
            enabled=True,
            puzzle_type="maths",
        )
        session = AlarmSession.create(user_id=user.id, device_serial=device.serial_number)

        valid = PuzzleSession.create(
            alarm_session_id=session.id,
            puzzle_type="maths",
            question="2 + 2",
            is_correct=True,
            time_taken_seconds=4,
            outcome_action=" Dismissed ",
        )
        invalid = PuzzleSession.create(
            alarm_session_id=session.id,
            puzzle_type="memory",
            question="Repeat pattern",
            is_correct=False,
            time_taken_seconds=7,
            outcome_action="ignored",
        )

        self.assertEqual(valid.outcome_action, "dismissed")
        self.assertIsNone(invalid.outcome_action)

    def test_explicit_puzzle_type_is_not_changed(self):
        """Explicit puzzle types should bypass the randomizer."""
        user = User.register("randomizer@example.com", "password123", "Randomizer")
        device = Device.register("TEST-RANDOM", "Clock", user)
        alarm = Alarm.create(
            device_serial=device.serial_number,
            user_id=user.id,
            time=time(7, 30),
            day_of_week=0,
            enabled=True,
            puzzle_type="memory",
        )

        self.assertEqual(resolve_effective_puzzle_type(alarm, device), "memory")

    def test_recommended_alarm_favors_puzzle_that_led_to_dismissal(self):
        """Recommended alarms should prefer puzzle types that led to dismissal."""
        user = User.register("randomizer2@example.com", "password123", "Randomizer")
        device = Device.register("TEST-RANDOM-2", "Clock", user)

        memory_session = AlarmSession.create(
            user_id=user.id,
            device_serial=device.serial_number,
            triggered_at=utc_now() - timedelta(days=2),
        )
        PuzzleSession.create(
            alarm_session_id=memory_session.id,
            puzzle_type="memory",
            question="Repeat pattern",
            is_correct=True,
            time_taken_seconds=12,
            outcome_action="snoozed",
        )

        maths_session = AlarmSession.create(
            user_id=user.id,
            device_serial=device.serial_number,
            triggered_at=utc_now() - timedelta(days=1),
        )
        PuzzleSession.create(
            alarm_session_id=maths_session.id,
            puzzle_type="maths",
            question="2 + 2",
            is_correct=True,
            time_taken_seconds=8,
            outcome_action="dismissed",
        )

        alarm = Alarm.create(
            device_serial=device.serial_number,
            user_id=user.id,
            time=time(8, 0),
            day_of_week=0,
            enabled=True,
            puzzle_type="recommended",
        )

        self.assertEqual(resolve_effective_puzzle_type(alarm, device), "maths")


if __name__ == "__main__":
    unittest.main()
