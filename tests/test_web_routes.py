"""Web route tests: auth flows, settings, and authenticated GET page rendering."""

import unittest
from datetime import time, timedelta

from tests.bootstrap import configure_test_environment, stub_optional_ml_dependencies


configure_test_environment()
stub_optional_ml_dependencies()

from app import app, database as db
from app.models import (
    Alarm,
    AlarmSession,
    Device,
    DifficultyModel,
    PuzzleSession,
    SleepSession,
    SleepStage,
    User,
)
from app.utils import utc_now


class WebRouteTests(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)
        app.config["WTF_CSRF_ENABLED"] = False
        db.drop_all()
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        app.config["WTF_CSRF_ENABLED"] = self.previous_csrf
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _log_in(self, user):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

    def test_login_redirects_on_success(self):
        """Valid login should redirect to the dashboard."""
        User.register("login@example.com", "password123", "Login")

        response = self.client.post(
            "/login",
            data={
                "email_address": "login@example.com",
                "password": "password123",
                "remember_me": "y",
                "submit": "Submit",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])

    def test_register_creates_user_and_logs_them_in(self):
        """Registering should create the user and log them in."""
        response = self.client.post(
            "/register",
            data={
                "email_address": "new@example.com",
                "preferred_name": "New",
                "password": "password123",
                "repeated_password": "password123",
                "submit": "Register",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])
        self.assertIsNotNone(User.query.filter_by(email_address="new@example.com").first())

    def test_pair_device_pairs_matching_code(self):
        """Entering a valid pairing code should attach the device to the user."""
        user = User.register("pair@example.com", "password123", "Pair")
        self._log_in(user)

        device = Device.register("PAIR-UI", "Clock", None)
        device.pairing_code = "ABC123"
        device.pairing_expiry = utc_now() + timedelta(minutes=5)
        db.session.commit()

        response = self.client.post(
            "/pair-device",
            data={"pairing_code": "abc123", "submit": "Confirm Pairing Code"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/account", response.headers["Location"])
        self.assertEqual(db.session.get(Device, device.serial_number).user_id, user.id)

    def test_device_settings_save_updates_name_and_snoozes(self):
        """Saving settings should update the device name and snooze limit."""
        user = User.register("settings@example.com", "password123", "Settings")
        device = Device.register("SETTINGS-1", "Old Name", user)
        self._log_in(user)

        response = self.client.post(
            f"/device/{device.serial_number}/settings",
            data={"name": "Bedroom", "max_snoozes": "5", "save": "Save"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        updated = db.session.get(Device, device.serial_number)
        self.assertEqual(updated.name, "Bedroom")
        self.assertEqual(updated.max_snoozes, 5)

    def test_device_settings_unpair_clears_owner(self):
        """Unpairing should clear the device owner."""
        user = User.register("unpair@example.com", "password123", "Unpair")
        device = Device.register("SETTINGS-2", "Clock", user)
        self._log_in(user)

        response = self.client.post(
            f"/device/{device.serial_number}/settings",
            data={"name": "Clock", "max_snoozes": "3", "unpair": "Unpair"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(db.session.get(Device, device.serial_number).user_id)

    def test_account_dashboard_and_alarms_pages_render(self):
        """Core account pages should render for a logged-in user."""
        user = User.register("pages@example.com", "password123", "Pages")
        device = Device.register("PAGES-1", "Bedroom", user)
        Alarm.create(
            device_serial=device.serial_number,
            user_id=user.id,
            time=time(7, 30),
            day_of_week=1,
            enabled=True,
            puzzle_type="memory",
        )
        self._log_in(user)

        account = self.client.get("/account")
        dashboard = self.client.get("/dashboard")
        alarms = self.client.get("/alarms")

        self.assertEqual(account.status_code, 200)
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(alarms.status_code, 200)
        self.assertIn(b"/account/session-history", account.data)
        self.assertIn(b"Overview", dashboard.data)
        self.assertIn(b"Next alarm", dashboard.data)        
        self.assertIn(b'id="alarms-grid"', alarms.data)

    def test_session_history_sleep_data_pair_device_and_add_alarm_render(self):
        """Secondary logged-in pages should render with the expected data."""
        user = User.register("pages2@example.com", "password123", "Pages")
        device = Device.register("PAGES-2", "Bedroom", user)
        alarm = Alarm.create(
            device_serial=device.serial_number,
            user_id=user.id,
            time=time(7, 30),
            day_of_week=1,
            enabled=True,
            puzzle_type="memory",
        )
        session = AlarmSession.create(
            user_id=user.id,
            device_serial=device.serial_number,
            triggered_at=utc_now() - timedelta(days=1),
            waking_difficulty=6,
        )
        PuzzleSession.create(
            alarm_session_id=session.id,
            puzzle_type="memory",
            question="Repeat pattern",
            is_correct=True,
            time_taken_seconds=9,
            outcome_action="dismissed",
        )
        db.session.add(SleepSession(
            user_id=user.id,
            start_date=utc_now() - timedelta(days=2, hours=8),
            end_date=utc_now() - timedelta(days=2),
            total_duration=7 * 3600,
        ))
        db.session.commit()
        self._log_in(user)

        session_history = self.client.get("/account/session-history?tz=UTC")
        sleep_data = self.client.get("/sleep-data")
        pair_device = self.client.get("/pair-device")
        add_alarm = self.client.get(f"/alarms/add?device={device.serial_number}")
        edit_alarm = self.client.get(f"/alarms/{alarm.id}/edit")

        self.assertEqual(session_history.status_code, 200)
        self.assertEqual(sleep_data.status_code, 200)
        self.assertEqual(pair_device.status_code, 200)
        self.assertEqual(add_alarm.status_code, 200)
        self.assertEqual(edit_alarm.status_code, 200)
        self.assertIn(
            f'/account/session-history/alarm/{session.id}/waking-difficulty'.encode(),
            session_history.data,
        )
        self.assertIn(b'name="pairing_code"', pair_device.data)
        self.assertIn(f'value="{device.serial_number}"'.encode(), add_alarm.data)
        self.assertIn(b'name="days_of_week"', add_alarm.data)
        self.assertIn(b'value="07:30"', edit_alarm.data)

    def test_delete_account_rejects_wrong_password(self):
        user = User.register("delete-fail@example.com", "password123", "DeleteFail")
        self._log_in(user)

        response = self.client.post(
            "/account/delete",
            data={
                "email_address": "delete-fail@example.com",
                "password": "wrong-password",
                "confirmation": "y",
                "submit": "Delete Account",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/account#delete-account", response.headers["Location"])
        self.assertIsNotNone(db.session.get(User, user.id))

    def test_delete_account_deletes_user_data_and_unpairs_devices(self):
        user = User.register("delete-ok@example.com", "password123", "DeleteOK")
        self._log_in(user)

        device = Device.register("DELETE-DEVICE-1", "Bedroom", user)
        alarm = Alarm.create(
            device_serial=device.serial_number,
            user_id=user.id,
            time=time(7, 30),
            day_of_week=1,
            enabled=True,
            puzzle_type="memory",
        )
        self.assertIsNotNone(alarm)

        alarm_session = AlarmSession.create(
            user_id=user.id,
            device_serial=device.serial_number,
            triggered_at=utc_now(),
            waking_difficulty=4,
        )
        PuzzleSession.create(
            alarm_session_id=alarm_session.id,
            puzzle_type="memory",
            question="Pattern",
            is_correct=True,
            time_taken_seconds=12,
            outcome_action="dismissed",
        )

        sleep_session = SleepSession(
            user_id=user.id,
            start_date=utc_now() - timedelta(hours=8),
            end_date=utc_now(),
            total_duration=7 * 3600,
        )
        db.session.add(sleep_session)
        db.session.flush()
        db.session.add(
            SleepStage(
                user_id=user.id,
                stage="Asleep",
                start_date=utc_now() - timedelta(hours=8),
                end_date=utc_now() - timedelta(hours=7),
                sleep_session_id=sleep_session.id,
            )
        )
        db.session.add(
            DifficultyModel(
                user_id=user.id,
                model_blob=b"model",
                last_trained=utc_now(),
            )
        )
        db.session.commit()

        response = self.client.post(
            "/account/delete",
            data={
                "email_address": "delete-ok@example.com",
                "password": "password123",
                "confirmation": "y",
                "submit": "Delete Account",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.headers["Location"])
        self.assertIsNone(db.session.get(User, user.id))
        self.assertIsNone(Alarm.query.filter_by(user_id=user.id).first())
        self.assertIsNone(AlarmSession.query.filter_by(user_id=user.id).first())
        self.assertIsNone(SleepSession.query.filter_by(user_id=user.id).first())
        self.assertIsNone(SleepStage.query.filter_by(user_id=user.id).first())
        self.assertIsNone(DifficultyModel.query.filter_by(user_id=user.id).first())

        refreshed_device = db.session.get(Device, device.serial_number)
        self.assertIsNotNone(refreshed_device)
        self.assertIsNone(refreshed_device.user_id)


if __name__ == "__main__":
    unittest.main()
