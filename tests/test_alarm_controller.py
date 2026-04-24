"""Alarm controller tests: queue handling, dismiss flow, snooze flow and puzzle fallback."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from tests.bootstrap import stub_optional_device_dependencies


stub_optional_device_dependencies()

from alarm.alarm_controller import Alarm, AlarmController
from alarm.io.input_handler import InputHandler
from alarm.io.output_handler import DebugOutputHandler


class _Tb:
    def post(self, data):
        return None


class _NoopInput(InputHandler):
    def __init__(self):
        super().__init__(_Tb())

    def check_inputs(self, state=None):
        return None


class _Buzzer:
    def __init__(self):
        self.play_calls = 0
        self.stop_calls = 0

    def play_alarm_sound(self):
        self.play_calls += 1

    def stop_alarm_sound(self):
        self.stop_calls += 1


class _Output:
    def __init__(self):
        self.buzzer = _Buzzer()
        self.messages = []

    def display_text(self, text):
        self.messages.append(text)


class _Puzzle:
    def __init__(self, solved=True, session_data=None):
        self.solved = solved
        self.session_data = session_data or {
            "alarm_session_id": "unused",
            "puzzle_type": "memory",
            "question": "Repeat pattern",
            "is_correct": True,
            "time_taken_seconds": 9.5,
            "outcome_action": None,
        }

    def run_puzzle(self):
        return self.solved

    def export_session(self, alarm_session_id):
        exported = dict(self.session_data)
        exported["alarm_session_id"] = alarm_session_id
        return exported


class AlarmControllerTests(unittest.TestCase):
    def test_check_alarms_triggers_due_enabled_alarm(self):
        """A due enabled alarm should trigger when the weekday and time match."""
        controller = AlarmController(_NoopInput(), _Output(), debug_mode=True)
        controller.alarms = [
            Alarm(
                id="alarm-due",
                time="07:30",
                enabled=True,
                day_of_week=0,
                puzzle_type="maths",
                max_snoozes=2,
                snooze_count=0,
                source_alarm_id="alarm-due",
            )
        ]
        now = datetime(2026, 4, 20, 7, 30, 0, tzinfo=timezone.utc)

        with patch("alarm.alarm_controller._clock_now", return_value=now):
            controller.update()
            triggered = controller.check_alarms()

        self.assertTrue(triggered)
        self.assertEqual(controller.state.name, "TRIGGERED")
        self.assertEqual(controller.current_triggered_alarm.id, "alarm-due")
        self.assertEqual(controller.output_handler.buzzer.play_calls, 1)

    def test_check_alarms_ignores_wrong_day_and_disabled_alarm(self):
        """Only enabled alarms for the current weekday should trigger."""
        controller = AlarmController(_NoopInput(), _Output(), debug_mode=True)
        controller.alarms = [
            Alarm(
                id="alarm-disabled",
                time="07:30",
                enabled=False,
                day_of_week=0,
                puzzle_type="maths",
                max_snoozes=2,
                snooze_count=0,
                source_alarm_id="alarm-disabled",
            ),
            Alarm(
                id="alarm-wrong-day",
                time="07:30",
                enabled=True,
                day_of_week=2,
                puzzle_type="memory",
                max_snoozes=2,
                snooze_count=0,
                source_alarm_id="alarm-wrong-day",
            ),
        ]
        now = datetime(2026, 4, 20, 7, 30, 0, tzinfo=timezone.utc)

        with patch("alarm.alarm_controller._clock_now", return_value=now):
            controller.update()
            triggered = controller.check_alarms()

        self.assertFalse(triggered)
        self.assertEqual(controller.state.name, "WAITING")
        self.assertIsNone(controller.current_triggered_alarm)
        self.assertEqual(controller.output_handler.buzzer.play_calls, 0)

    def test_check_alarms_does_not_retrigger_same_occurrence(self):
        """The same alarm occurrence should not fire twice in the same second."""
        controller = AlarmController(_NoopInput(), _Output(), debug_mode=True)
        alarm = Alarm(
            id="alarm-repeat",
            time="07:30",
            enabled=True,
            day_of_week=0,
            puzzle_type="maths",
            max_snoozes=2,
            snooze_count=0,
            source_alarm_id="alarm-repeat",
        )
        controller.alarms = [alarm]
        now = datetime(2026, 4, 20, 7, 30, 0, tzinfo=timezone.utc)

        with patch("alarm.alarm_controller._clock_now", return_value=now):
            controller.update()
            first = controller.check_alarms()
            controller.stop_alarm()
            controller.current_time = "07:30:00"
            second = controller.check_alarms()

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(controller.output_handler.buzzer.play_calls, 1)
        self.assertTrue(alarm.enabled)
        self.assertEqual(controller.state.name, "WAITING")

    def test_waiting_state_displays_current_time(self):
        """The waiting state should show the current time on the display."""
        controller = AlarmController(_NoopInput(), _Output(), debug_mode=True)
        controller.sensor.get_temp_and_humidity = lambda: (21, 55)
        now = datetime(2026, 4, 20, 7, 31, 12, tzinfo=timezone.utc)

        with patch("alarm.alarm_controller._clock_now", return_value=now):
            controller.update()
            triggered = controller.check_alarms()

        self.assertFalse(triggered)
        self.assertEqual(controller.state.name, "WAITING")
        self.assertEqual(controller.output_handler.messages[-1], "     07:31\n21c 55%")

    def test_completed_sessions_removed_only_when_dropped(self):
        """Completed sessions should stay queued until upload success is confirmed."""
        controller = AlarmController(_NoopInput(), DebugOutputHandler())
        controller._complete_sessions["session-1"] = {
            "triggered_at": "2026-04-19T07:30:00+00:00",
            "puzzle_sessions": [],
        }

        first_peek = controller.peek_complete_sessions()
        second_peek = controller.peek_complete_sessions()

        self.assertEqual(first_peek, second_peek)
        self.assertIn("session-1", controller.peek_complete_sessions())

        controller.drop_complete_sessions(["session-1"])

        self.assertEqual(controller.peek_complete_sessions(), {})

    def test_dismiss_moves_session_to_completed_queue(self):
        """Dismissing an alarm should move the session to the completed queue."""
        controller = AlarmController(_NoopInput(), _Output(), debug_mode=True)
        alarm = Alarm(
            id="alarm-1",
            time="07:30",
            enabled=True,
            day_of_week=0,
            puzzle_type="memory",
            max_snoozes=3,
            snooze_count=0,
            source_alarm_id="source-1",
        )
        fake_puzzle = _Puzzle()

        controller.trigger_alarm(alarm)
        controller._build_puzzle_for_current_alarm = lambda: fake_puzzle
        controller._decision_selection = lambda options: "dismiss"
        controller._get_user_waking_difficulty = lambda: 8

        controller.run_alarm_interaction()

        completed = controller.peek_complete_sessions()
        self.assertIsNone(controller.current_triggered_alarm)
        self.assertEqual(controller.state.name, "WAITING")
        self.assertNotIn("source-1", controller._pending_sessions)
        self.assertIn("source-1", completed)
        self.assertEqual(completed["source-1"]["waking_difficulty"], 8)
        self.assertEqual(completed["source-1"]["puzzle_sessions"][-1]["outcome_action"], "dismissed")

    def test_snooze_keeps_session_pending_creates_snooze_alarm(self):
        """Snoozing an alarm should keep the session pending and create a new snooze alarm."""
        controller = AlarmController(_NoopInput(), _Output(), debug_mode=True)
        alarm = Alarm(
            id="alarm-2",
            time="07:30",
            enabled=True,
            day_of_week=0,
            puzzle_type="maths",
            max_snoozes=2,
            snooze_count=0,
            source_alarm_id="source-2",
        )
        fake_puzzle = _Puzzle(session_data={
            "alarm_session_id": "unused",
            "puzzle_type": "maths",
            "question": "2 + 2",
            "is_correct": True,
            "time_taken_seconds": 4.2,
            "outcome_action": None,
        })

        controller.trigger_alarm(alarm)
        controller._build_puzzle_for_current_alarm = lambda: fake_puzzle
        controller._decision_selection = lambda options: "snooze"

        controller.run_alarm_interaction()

        pending = controller._pending_sessions["source-2"]
        self.assertEqual(controller.state.name, "WAITING")
        self.assertEqual(len(controller.snooze_alarms), 1)
        self.assertEqual(controller.snooze_alarms[0].snooze_count, 1)
        self.assertEqual(pending["puzzle_sessions"][-1]["outcome_action"], "snoozed")
        self.assertEqual(controller.peek_complete_sessions(), {})

    def test_timeout_resumes_alarm_sound(self):
        """A timed-out puzzle should retrigger the alarm sound."""
        controller = AlarmController(_NoopInput(), _Output(), debug_mode=True)
        alarm = Alarm(
            id="alarm-timeout",
            time="07:30",
            enabled=True,
            day_of_week=0,
            puzzle_type="maths",
            max_snoozes=2,
            snooze_count=0,
            source_alarm_id="source-timeout",
        )
        timeout_puzzle = _Puzzle(
            solved=False,
            session_data={
                "alarm_session_id": "unused",
                "puzzle_type": "maths",
                "question": "2 + 2",
                "is_correct": False,
                "time_taken_seconds": 120.0,
                "outcome_action": None,
            },
        )

        controller.trigger_alarm(alarm)
        controller._build_puzzle_for_current_alarm = lambda: timeout_puzzle

        controller.run_alarm_interaction()

        self.assertEqual(controller.output_handler.buzzer.stop_calls, 1)
        self.assertEqual(controller.output_handler.buzzer.play_calls, 2)
        self.assertEqual(controller.state.name, "TRIGGERED")
        self.assertEqual(controller.current_triggered_alarm.id, "alarm-timeout")

    def test_unknown_puzzle_type_falls_back_to_maths(self):
        """If an alarm has an unknown puzzle type, it should fall back to a default puzzle type."""
        controller = AlarmController(_NoopInput(), _Output())
        controller.current_triggered_alarm = Alarm(
            id="alarm-3",
            time="07:30",
            enabled=True,
            day_of_week=0,
            puzzle_type="something-else",
            max_snoozes=3,
            snooze_count=0,
            source_alarm_id="source-3",
        )

        puzzle = controller._build_puzzle_for_current_alarm()

        self.assertEqual(puzzle.__class__.__name__, "MathsPuzzle")


if __name__ == "__main__":
    unittest.main()
