"""Helper tests: time parsing, timezone fallback, sleep stats and sparse-model behavior."""

import unittest
from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch

from tests.bootstrap import configure_test_environment, stub_optional_ml_dependencies


configure_test_environment()
stub_optional_ml_dependencies()

from app import app, database as db
from app.analysis import _compute_sleep_statistics, find_suitable_alarm, should_retrain_model
from app.models import AlarmSession, Device, DifficultyModel, PuzzleSession, SleepSession, SleepStage, User
from app.utils import group_sleep_records, parse_apple_dt, resolve_timezone, next_weekday_utc


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()

        self.user = User.register("helpers@example.com", "password123", "Helpers")
        self.device = Device.register("TEST-HELPERS", "Clock", self.user)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_group_sleep_records_and_parse_apple_dt(self):
        """Sleep records should group by night and parse Apple timestamps."""
        first_start = parse_apple_dt("2026-04-19T22:00:00+0000")
        first_end = parse_apple_dt("2026-04-19T23:00:00+0000")
        second_start = parse_apple_dt("2026-04-19T23:30:00+0000")
        second_end = parse_apple_dt("2026-04-20T01:00:00+0000")
        third_start = parse_apple_dt("2026-04-20T04:30:00+0000")
        third_end = parse_apple_dt("2026-04-20T06:00:00+0000")

        grouped = group_sleep_records([
            {"start_time": third_start, "end_time": third_end},
            {"start_time": first_start, "end_time": first_end},
            {"start_time": second_start, "end_time": second_end},
        ])

        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(grouped[0]), 2)
        self.assertEqual(first_start.tzinfo, timezone.utc)

        with self.assertRaises(ValueError):
            parse_apple_dt(" ")

    def test_next_weekday_utc_and_resolve_timezone(self):
        """Weekday rollover and bad timezones should fall back correctly."""
        fake_now = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)  # Monday

        with patch("app.utils.utc_now", return_value=fake_now):
            candidate = next_weekday_utc(day_of_week=0, time_value=time(7, 30))

        self.assertEqual(candidate, datetime(2026, 4, 27, 7, 30, tzinfo=timezone.utc))

        display_tz, active_tz = resolve_timezone("Not/A_Real_Zone")
        self.assertEqual(display_tz, timezone.utc)
        self.assertEqual(active_tz, "UTC")

    def test_compute_sleep_statistics(self):
        """Sleep statistics should compute quality and efficiency from stages."""
        sleep_session = SleepSession(
            user_id=self.user.id,
            start_date=datetime(2026, 4, 19, 22, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 4, 20, 6, 0, tzinfo=timezone.utc),
            total_duration=7 * 3600,
        )
        db.session.add(sleep_session)
        db.session.flush()

        db.session.add(SleepStage(
            user_id=self.user.id,
            stage="AsleepCore",
            start_date=datetime(2026, 4, 19, 22, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 4, 20, 1, 0, tzinfo=timezone.utc),
            sleep_session_id=sleep_session.id,
        ))
        db.session.add(SleepStage(
            user_id=self.user.id,
            stage="Awake",
            start_date=datetime(2026, 4, 20, 1, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 4, 20, 2, 0, tzinfo=timezone.utc),
            sleep_session_id=sleep_session.id,
        ))
        db.session.add(SleepStage(
            user_id=self.user.id,
            stage="AsleepDeep",
            start_date=datetime(2026, 4, 20, 2, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 4, 20, 6, 0, tzinfo=timezone.utc),
            sleep_session_id=sleep_session.id,
        ))
        db.session.commit()

        quality_by_id, efficiency_by_id = _compute_sleep_statistics([SleepSession.query.one()])

        self.assertAlmostEqual(quality_by_id[sleep_session.id], 100.0)
        self.assertAlmostEqual(efficiency_by_id[sleep_session.id], 87.5)

    def test_should_retrain_model_and_find_suitable_alarm(self):
        """Model checks should retrain when missing and reject sparse alarm data."""
        self.assertTrue(should_retrain_model(self.user.id))

        db.session.add(DifficultyModel(
            user_id=self.user.id,
            model_blob=b"pretend-model",
            last_trained=datetime.now(timezone.utc) - timedelta(days=2),
        ))
        db.session.commit()

        self.assertFalse(should_retrain_model(self.user.id, max_age_days=7))

        for index in range(3):
            session = AlarmSession.create(
                user_id=self.user.id,
                device_serial=self.device.serial_number,
                triggered_at=datetime.now(timezone.utc) - timedelta(days=index + 1),
                waking_difficulty=5,
            )
            PuzzleSession.create(
                alarm_session_id=session.id,
                puzzle_type="maths",
                question="1 + 1",
                is_correct=True,
                time_taken_seconds=5,
                outcome_action="dismissed",
            )

        result = find_suitable_alarm(
            user_id=self.user.id,
            min_time=datetime.now(timezone.utc).replace(hour=23, minute=0, second=0, microsecond=0),
            max_time=(datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=1, minute=0, second=0, microsecond=0),
        )

        self.assertEqual(result["reason"], "not_enough_alarm_data")
        self.assertEqual(result["current_sessions"], 3)
        self.assertEqual(result["required_sessions"], 10)


if __name__ == "__main__":
    unittest.main()
