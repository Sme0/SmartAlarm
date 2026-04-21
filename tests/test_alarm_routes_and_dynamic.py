"""Alarm route tests: CRUD behavior plus dynamic-alarm scheduling safeguards."""

import unittest
from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch

from tests.bootstrap import configure_test_environment, stub_optional_ml_dependencies


configure_test_environment()
stub_optional_ml_dependencies()

from app import app, database as db
from app.models import Alarm, AlarmSession, Device, User
from app.routes import _run_dynamic_alarm_optimization


class AlarmRouteTests(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)
        app.config["WTF_CSRF_ENABLED"] = False
        db.drop_all()
        db.create_all()

        self.client = app.test_client()
        self.user = User.register("alarm@example.com", "password123", "Alarm")
        self.other_user = User.register("other-alarm@example.com", "password123", "Other")
        self.device = Device.register("TEST-ALARM", "Clock", self.user)
        self.other_device = Device.register("TEST-OTHER-ALARM", "Clock", self.other_user)

        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
            session["_fresh"] = True

    def tearDown(self):
        app.config["WTF_CSRF_ENABLED"] = self.previous_csrf
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_api_create_alarm_creates_one_per_day(self):
        """Creating alarms for multiple days should create one row per day."""
        response = self.client.post(
            "/api/alarms/create",
            json={
                "device_serial": self.device.serial_number,
                "time": "07:30",
                "days_of_week": [1, 3],
                "puzzle_type": "memory",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Alarm.query.count(), 2)

        created_days = sorted(alarm.day_of_week for alarm in Alarm.query.order_by(Alarm.day_of_week.asc()).all())
        created_types = {alarm.puzzle_type for alarm in Alarm.query.all()}
        self.assertEqual(created_days, [1, 3])
        self.assertEqual(created_types, {"memory"})

    def test_api_delete_alarm_rejects_other_users_alarm(self):
        """Users should not be able to delete another user's alarm."""
        alarm = Alarm.create(
            device_serial=self.other_device.serial_number,
            user_id=self.other_user.id,
            time=time(8, 0),
            day_of_week=2,
            enabled=True,
            puzzle_type="maths",
        )

        response = self.client.post("/api/alarms/delete", json={"alarm_id": alarm.id})

        self.assertEqual(response.status_code, 403)
        self.assertIsNotNone(db.session.get(Alarm, alarm.id))

    def test_add_alarm_dynamic_before_unlock_falls_back_to_static(self):
        """Dynamic alarms should fall back to static until the feature is unlocked."""
        response = self.client.post(
            "/alarms/add",
            data={
                "device": self.device.serial_number,
                "time": "07:45",
                "use_dynamic_alarm": "y",
                "dynamic_start_time": "07:00",
                "dynamic_end_time": "08:00",
                "days_of_week": ["1", "4"],
                "puzzle_type": "random",
                "submit": "Save Alarm",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        alarms = Alarm.query.order_by(Alarm.day_of_week.asc()).all()
        self.assertEqual(len(alarms), 2)
        self.assertTrue(all(alarm.use_dynamic_alarm is False for alarm in alarms))
        self.assertTrue(all(alarm.dynamic_start_time is None for alarm in alarms))
        self.assertTrue(all(alarm.dynamic_end_time is None for alarm in alarms))
        self.assertEqual({alarm.time.strftime("%H:%M") for alarm in alarms}, {"07:45"})

    def test_dynamic_alarm_optimization_updates_alarm_when_state_matches(self):
        """Optimization should update the alarm when the saved state still matches."""
        alarm = Alarm.create(
            device_serial=self.device.serial_number,
            user_id=self.user.id,
            time=time(7, 0),
            day_of_week=1,
            enabled=True,
            puzzle_type="random",
            use_dynamic_alarm=True,
            dynamic_start_time=time(6, 30),
            dynamic_end_time=time(7, 30),
        )

        with patch("app.routes._resolve_alarm_time", return_value=(time(6, 45), True)):
            _run_dynamic_alarm_optimization(
                alarm_id=alarm.id,
                user_id=self.user.id,
                day_of_week=alarm.day_of_week,
                preferred_time=alarm.time,
                dynamic_start_time=alarm.dynamic_start_time,
                dynamic_end_time=alarm.dynamic_end_time,
                expected_alarm_time=alarm.time,
                expected_dynamic_start_time=alarm.dynamic_start_time,
                expected_dynamic_end_time=alarm.dynamic_end_time,
            )

        db.session.expire_all()
        self.assertEqual(db.session.get(Alarm, alarm.id).time.strftime("%H:%M"), "06:45")

    def test_dynamic_alarm_optimization_skips_stale_update(self):
        """Optimization should not overwrite alarms changed after the job was queued."""
        alarm = Alarm.create(
            device_serial=self.device.serial_number,
            user_id=self.user.id,
            time=time(7, 0),
            day_of_week=1,
            enabled=True,
            puzzle_type="random",
            use_dynamic_alarm=True,
            dynamic_start_time=time(6, 30),
            dynamic_end_time=time(7, 30),
        )
        alarm.time = time(7, 20)
        db.session.commit()

        with patch("app.routes._resolve_alarm_time", return_value=(time(6, 45), True)):
            _run_dynamic_alarm_optimization(
                alarm_id=alarm.id,
                user_id=self.user.id,
                day_of_week=alarm.day_of_week,
                preferred_time=time(7, 0),
                dynamic_start_time=alarm.dynamic_start_time,
                dynamic_end_time=alarm.dynamic_end_time,
                expected_alarm_time=time(7, 0),
                expected_dynamic_start_time=alarm.dynamic_start_time,
                expected_dynamic_end_time=alarm.dynamic_end_time,
            )

        db.session.expire_all()
        self.assertEqual(db.session.get(Alarm, alarm.id).time.strftime("%H:%M"), "07:20")


if __name__ == "__main__":
    unittest.main()
