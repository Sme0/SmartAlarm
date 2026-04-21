"""Device route tests: pairing, alarm fetches and completed-session uploads."""

import unittest
from datetime import timedelta, time

from tests.bootstrap import configure_test_environment, stub_optional_ml_dependencies


configure_test_environment()
stub_optional_ml_dependencies()

from app import app, database as db
from app.models import Alarm, AlarmSession, Device, PuzzleSession, User
from app.utils import utc_now


class DeviceRouteTests(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()

        self.client = app.test_client()
        self.user = User.register("device@example.com", "password123", "Device")
        self.device = Device.register("TEST-DEVICE", "Clock", self.user)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_submit_complete_sessions_persists_puzzles_and_waking_difficulty(self):
        """The device upload endpoint should store alarm session metadata and puzzle outcomes."""
        response = self.client.post("/api/device/submit-complete-sessions", json={
            "serial_number": self.device.serial_number,
            "complete_sessions": {
                "session-1": {
                    "triggered_at": "2026-04-19T07:30:00+00:00",
                    "waking_difficulty": 7,
                    "puzzle_sessions": [
                        {
                            "puzzle_type": "memory",
                            "question": "Repeat pattern",
                            "is_correct": True,
                            "time_taken_seconds": 11.6,
                            "outcome_action": "snoozed",
                        },
                        {
                            "puzzle_type": "maths",
                            "question": "2 + 2",
                            "is_correct": True,
                            "time_taken_seconds": 4.2,
                            "outcome_action": "dismissed",
                        },
                    ],
                }
            },
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["response"], "ok")

        alarm_session = AlarmSession.query.one()
        puzzle_sessions = PuzzleSession.query.order_by(PuzzleSession.id.asc()).all()

        self.assertEqual(alarm_session.user_id, self.user.id)
        self.assertEqual(alarm_session.device_serial, self.device.serial_number)
        self.assertEqual(alarm_session.waking_difficulty, 7)
        self.assertEqual(len(puzzle_sessions), 2)
        self.assertEqual(puzzle_sessions[0].outcome_action, "snoozed")
        self.assertEqual(puzzle_sessions[1].outcome_action, "dismissed")
        self.assertEqual(puzzle_sessions[0].time_taken_seconds, 12)
        self.assertEqual(puzzle_sessions[1].time_taken_seconds, 4)

    def test_invalid_session_upload_leaves_no_partial_rows(self):
        """Invalid upload payloads should fail without storing partial alarm sessions."""
        response = self.client.post("/api/device/submit-complete-sessions", json={
            "serial_number": self.device.serial_number,
            "complete_sessions": {
                "bad-session": {
                    "triggered_at": "2026-04-19T07:30:00+00:00",
                    "puzzle_sessions": "not-a-list",
                }
            },
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(AlarmSession.query.count(), 0)
        self.assertEqual(PuzzleSession.query.count(), 0)

    def test_request_pairing_code_creates_device_and_reuses_code(self):
        """Requesting a pairing code twice should reuse the unexpired code."""
        first_response = self.client.post(
            "/api/device/request-pairing-code",
            json={"serial_number": "PAIR-DEVICE-1"},
        )
        second_response = self.client.post(
            "/api/device/request-pairing-code",
            json={"serial_number": "PAIR-DEVICE-1"},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        first_code = first_response.get_json()["pairing_code"]
        second_code = second_response.get_json()["pairing_code"]
        device = db.session.get(Device, "PAIR-DEVICE-1")

        self.assertIsNotNone(device)
        self.assertEqual(first_code, second_code)
        self.assertEqual(device.pairing_code, first_code)

    def test_pairing_status_reports_expired_code(self):
        """Expired pairing codes should return a failed status."""
        device = Device.register("PAIR-2", "Clock", None)
        device.pairing_code = "ABC123"
        device.pairing_expiry = utc_now() - timedelta(minutes=1)
        db.session.commit()

        response = self.client.post(
            "/api/device/pairing-status",
            json={"serial_number": device.serial_number},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["response"], "failed")

    def test_get_alarms_returns_device_alarms_and_updates_heartbeat(self):
        """Fetching alarms should return only that device's alarms and update heartbeat."""
        paired_device = Device.register("PAIR-3", "Clock A", self.user)
        other_device = Device.register("PAIR-4", "Clock B", self.user)

        target_alarm = Alarm.create(
            device_serial=paired_device.serial_number,
            user_id=self.user.id,
            time=time(7, 0),
            day_of_week=1,
            enabled=True,
            puzzle_type="recommended",
        )
        Alarm.create(
            device_serial=other_device.serial_number,
            user_id=self.user.id,
            time=time(8, 30),
            day_of_week=2,
            enabled=True,
            puzzle_type="memory",
        )

        session = AlarmSession.create(
            user_id=self.user.id,
            device_serial=paired_device.serial_number,
            triggered_at=utc_now() - timedelta(days=1),
        )
        PuzzleSession.create(
            alarm_session_id=session.id,
            puzzle_type="maths",
            question="2 + 2",
            is_correct=True,
            time_taken_seconds=4,
            outcome_action="dismissed",
        )

        response = self.client.post(
            "/api/device/get-alarms",
            json={"serial_number": paired_device.serial_number},
        )

        self.assertEqual(response.status_code, 200)
        alarms = response.get_json()["alarms"]
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0]["id"], target_alarm.id)
        self.assertEqual(alarms[0]["puzzle_type"], "maths")
        self.assertEqual(alarms[0]["max_snoozes"], 3)
        self.assertIsNotNone(db.session.get(Device, paired_device.serial_number).last_seen)


if __name__ == "__main__":
    unittest.main()
