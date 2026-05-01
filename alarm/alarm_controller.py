"""Alarm controller state machine for triggering alarms and running puzzles."""

import os
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytz

from alarm.alarm_state import AlarmState
from alarm.io.input_handler import InputEventType, InputHandler
from alarm.io.output_handler import DebugOutputHandler, OutputHandler
from alarm.io.pi_bluetooth import BluetoothConfirmation
from alarm.io.temp_sensor import DebugTempSensor, RaspberryPiTempSensor
from alarm.puzzles.maths_puzzle import MathsPuzzle
from alarm.puzzles.memory_puzzle import MemoryPuzzle
from alarm.puzzles.puzzle import Puzzle

from alarm.device_cache import (
    can_collect_alarm_sessions,
    can_collect_brainteaser_performance,
    can_ask_waking_difficulty,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Return timezone-aware UTC timestamp for session logging."""
    return datetime.now(timezone.utc)


def _resolve_clock_timezone():
    """
    Resolve timezone in this priority:
    1) DEVICE_TIMEZONE env var (e.g. Europe/London)
    2) OS/device local timezone
    3) UTC fallback
    """
    configured_tz = (os.getenv("DEVICE_TIMEZONE") or "").strip()
    if configured_tz:
        try:
            return pytz.timezone(configured_tz)
        except pytz.UnknownTimeZoneError:
            logger.warning(
                f"Invalid DEVICE_TIMEZONE '{configured_tz}', falling back to device timezone"
            )

    local_tz = datetime.now().astimezone().tzinfo
    return local_tz or timezone.utc


CLOCK_TIMEZONE = _resolve_clock_timezone()


def _clock_now() -> datetime:
    """Return current time in the resolved device timezone."""
    return datetime.now(CLOCK_TIMEZONE)


def _get_current_day_of_week_number():
    """
    Returns the current day of the week as a number (Monday=0, Sunday=6)
    """
    return _clock_now().weekday()


@dataclass
class Alarm:
    """Runtime alarm representation synced from the server."""

    id: str
    time: str
    enabled: bool
    day_of_week: int
    puzzle_type: str
    max_snoozes: int
    snooze_count: int
    source_alarm_id: str


class AlarmController:
    """Manage alarm state transitions, puzzles, and session telemetry."""

    def __init__(
        self,
        input_handler: InputHandler,
        output_handler: OutputHandler,
        debug_mode: bool = False,
    ):

        self.input_handler = input_handler
        self.output_handler = output_handler
        self.debug_mode = debug_mode

        # Current time in 24-hour format
        self.current_time = 0
        self.last_displayed_minute = None
        self.last_triggered_occurrence_key = None

        # Alarms in 24-hour format
        self.alarms: List[Alarm] = []
        self.snooze_alarms: List[Alarm] = []

        # Current alarm state
        self.state: AlarmState = AlarmState.WAITING
        self.current_triggered_alarm: Optional[Alarm] = None

        # Session data
        self._pending_sessions: Dict[str, Dict[str, Any]] = {}
        self._complete_sessions: Dict[str, Dict[str, Any]] = {}

        self.bluetooth_connection = BluetoothConfirmation(20, True)

        self.sensor = DebugTempSensor() if self.debug_mode else RaspberryPiTempSensor()

    def _build_puzzle_for_current_alarm(self) -> Puzzle:
        """
        Create the puzzle instance for the active alarm.
        Defaults to maths if the alarm is missing or has an unknown type.
        """
        puzzle_type = (
            (getattr(self.current_triggered_alarm, "puzzle_type", "") or "")
            .strip()
            .lower()
        )
        if puzzle_type == "memory":
            return MemoryPuzzle(self.input_handler, self.output_handler)
        return MathsPuzzle(self.input_handler, self.output_handler)

    def _decision_selection(self, options: List[str]) -> Optional[str]:
        """Prompt a two-option choice on the LCD and return the selected label."""
        MAX_TIME = 30
        selected_idx = 0
        start_time = time.time()

        update_display = True

        while True:
            if time.time() - start_time > MAX_TIME:
                return "trigger"

            if update_display:
                rendered_options = options.copy()
                rendered_options[selected_idx] = f">{options[selected_idx]}<"
                self.output_handler.display_text("\n".join(rendered_options))
                update_display = False

            self.input_handler.check_inputs()
            events = self.input_handler.pop_events_by_type(
                {
                    InputEventType.JOYSTICK_LEFT,
                    InputEventType.JOYSTICK_RIGHT,
                    InputEventType.JOYSTICK_PRESS,
                    InputEventType.ALARM_DISMISS,
                }
            )

            if not events:
                time.sleep(0.05)
                continue

            for event in events:
                if event.event_type in [
                    InputEventType.JOYSTICK_PRESS,
                    InputEventType.ALARM_DISMISS,
                ]:
                    return options[selected_idx]

                if len(options) == 1:
                    continue

                if event.event_type == InputEventType.JOYSTICK_LEFT:
                    selected_idx = (selected_idx - 1) % len(options)
                    update_display = True
                elif event.event_type == InputEventType.JOYSTICK_RIGHT:
                    selected_idx = (selected_idx + 1) % len(options)
                    update_display = True

    def _get_user_waking_difficulty(self):
        """Ask the user for a 1-10 waking difficulty score via joystick input."""
        MAX_TIME = 60
        selected_value = 5
        start_time = time.time()

        update_display = True

        while True:
            if time.time() - start_time > MAX_TIME:
                return None

            if update_display:
                output = f"Waking\ndifficulty: >{selected_value}<"
                self.output_handler.display_text(output)
                update_display = False

            self.input_handler.check_inputs()
            events = self.input_handler.pop_events_by_type(
                {
                    InputEventType.JOYSTICK_LEFT,
                    InputEventType.JOYSTICK_RIGHT,
                    InputEventType.JOYSTICK_UP,
                    InputEventType.JOYSTICK_DOWN,
                    InputEventType.JOYSTICK_PRESS,
                    InputEventType.ALARM_DISMISS,
                }
            )

            if not events:
                time.sleep(0.05)
                continue

            for event in events:
                if event.event_type in [
                    InputEventType.JOYSTICK_PRESS,
                    InputEventType.ALARM_DISMISS,
                ]:
                    return selected_value

                if event.event_type in [
                    InputEventType.JOYSTICK_LEFT,
                    InputEventType.JOYSTICK_DOWN,
                ]:
                    selected_value = max(1, selected_value - 1)
                    update_display = True
                elif event.event_type in [
                    InputEventType.JOYSTICK_RIGHT,
                    InputEventType.JOYSTICK_UP,
                ]:
                    selected_value = min(10, selected_value + 1)
                    update_display = True

    def update(self):
        """Update the cached current time string used by alarm checks."""
        # Update current time
        self.current_time = _clock_now().strftime("%H:%M:%S")

    def check_alarms(self) -> bool:
        """
        Checks if there are any alarms due to trigger.
        :return: If an alarm has been triggered
        """
        now = _clock_now()
        current_minute = now.minute
        day_of_week = now.weekday()

        # Check each alarm and trigger if needed
        alarms_to_check = (self.alarms or []) + (self.snooze_alarms or [])
        for alarm in alarms_to_check:
            occurrence_key = (
                str(alarm.id),
                now.date().isoformat(),
                alarm.time,
            )
            if (
                self.state == AlarmState.WAITING
                and alarm.enabled
                and day_of_week == alarm.day_of_week
                and self.current_time == (alarm.time + ":00")
                and occurrence_key != self.last_triggered_occurrence_key
            ):
                self.last_triggered_occurrence_key = occurrence_key
                self.trigger_alarm(alarm)
                return True

        # If there are no alarms triggered
        if (
            self.state == AlarmState.WAITING
            and current_minute != self.last_displayed_minute
        ):
            self.last_displayed_minute = current_minute

            temp, humidity = self.sensor.get_temp_and_humidity()
            self.input_handler.thingsboard_client.post({
                "temp_c": int(temp),
                "humidity_pct": int(humidity),
            })

            self.output_handler.display_text(
                f"     {_clock_now().strftime('%H:%M')}\n{temp}c {humidity}%"
            )

        return False

    def trigger_alarm(self, current_alarm):
        """
        Triggers the specified alarm.
        :param current_alarm: The alarm to be triggered
        :return:
        """
        self.state = AlarmState.TRIGGERED
        self.current_triggered_alarm = current_alarm

        source_alarm_id = str(current_alarm.source_alarm_id or current_alarm.id)

        # Only create a session if permission is enabled at trigger time
        if can_collect_alarm_sessions():
            self._pending_sessions.setdefault(
                source_alarm_id,
                {
                    "triggered_at": _utc_now().isoformat(),
                    "puzzle_sessions": [],
                    "permissions": {
                        "collect_brainteaser_performance": can_collect_brainteaser_performance(),
                        "ask_waking_difficulty": can_ask_waking_difficulty(),
                    },
                },
            )
            self.input_handler.thingsboard_client.post({
                "alarm_event": "triggered",
                "alarm_id": str(current_alarm.id),
                "source_alarm_id": source_alarm_id,
                "alarm_time": current_alarm.time,
                "alarm_day_of_week": current_alarm.day_of_week,
                "puzzle_type": current_alarm.puzzle_type,
            })

        self.output_handler.display_text(
            f"Alarm Triggered: {_clock_now().strftime('%H:%M')}"
        )
        self.output_handler.buzzer.play_alarm_sound()
        if isinstance(self.output_handler, DebugOutputHandler):
            print("Type 'dismiss' to solve puzzle.")

    def run_alarm_interaction(self):
        """Handle puzzle flow, confirmation button, and snooze/dismiss choice."""

        if not self.current_triggered_alarm:
            return

        self.state = AlarmState.PUZZLE

        self.output_handler.buzzer.stop_alarm_sound()
        puzzle = self._build_puzzle_for_current_alarm()
        solved = puzzle.run_puzzle()
        source_alarm_id = str(
            self.current_triggered_alarm.source_alarm_id
            or self.current_triggered_alarm.id
        )
        session = self._pending_sessions.get(source_alarm_id)
        exported_session = None

        # Only append puzzle session if both permissions are enabled AND session exists
        if session and session.get("permissions", {}).get("collect_brainteaser_performance", True):
            exported_session = puzzle.export_session(source_alarm_id)
            session["puzzle_sessions"].append(exported_session)

        if not solved:
            if session and exported_session is not None:
                exported_session["outcome_action"] = "triggered"
                self.input_handler.thingsboard_client.post({
                    "puzzle_type": exported_session.get("puzzle_type"),
                    "puzzle_time_taken_seconds": exported_session.get("time_taken_seconds"),
                    "puzzle_is_correct": exported_session.get("is_correct"),
                    "puzzle_outcome_action": exported_session.get("outcome_action"),
                })
            self.trigger_alarm(self.current_triggered_alarm)
            return

        # Skip Bluetooth confirmation in debug mode
        if not self.debug_mode:
            self.output_handler.display_text("Get up and press\nthe button")
            self.bluetooth_connection.send_confirmation_request()
            self.bluetooth_connection.await_confirmation()
            confirmed = self.bluetooth_connection.check_confirmation()

            if not confirmed:
                self.trigger_alarm(self.current_triggered_alarm)
                return

        options = ["Dismiss"]

        max_snoozes = max(0, int(self.current_triggered_alarm.max_snoozes))
        current_snooze_count = self.current_triggered_alarm.snooze_count
        if not current_snooze_count >= max_snoozes:
            options.append("Snooze")

        # Clear events before form
        self.input_handler.pop_events()
        choice = self._decision_selection(options)
        if choice:
            choice = choice.lower()

        if choice == "snooze":
            # TODO: Make snooze time editable through web
            if session and session.get("puzzle_sessions"):
                session["puzzle_sessions"][-1]["outcome_action"] = "snoozed"
                last_session = session["puzzle_sessions"][-1]
                self.input_handler.thingsboard_client.post({
                    "puzzle_type": last_session.get("puzzle_type"),
                    "puzzle_time_taken_seconds": last_session.get("time_taken_seconds"),
                    "puzzle_is_correct": last_session.get("is_correct"),
                    "puzzle_outcome_action": last_session.get("outcome_action"),
                })
            snooze_time = (_clock_now() + timedelta(minutes=5)).strftime("%H:%M")
            source_alarm_id = (
                self.current_triggered_alarm.source_alarm_id
                or self.current_triggered_alarm.id
            )
            self.snooze_alarms.append(
                Alarm(
                    id=f"{source_alarm_id}-Snooze-{current_snooze_count + 1}",
                    time=snooze_time,
                    enabled=True,
                    day_of_week=_get_current_day_of_week_number(),
                    puzzle_type=self.current_triggered_alarm.puzzle_type,
                    max_snoozes=max_snoozes,
                    snooze_count=current_snooze_count + 1,
                    source_alarm_id=source_alarm_id,
                )
            )
            if can_collect_alarm_sessions():
                self.input_handler.thingsboard_client.post({
                    "alarm_event": "snoozed",
                    "alarm_id": str(self.current_triggered_alarm.id),
                    "source_alarm_id": source_alarm_id,
                    "snooze_count": current_snooze_count + 1,
                })
            self.stop_alarm()

        elif choice == "dismiss":
            waking_difficulty = None
            if session and session.get("permissions", {}).get("ask_waking_difficulty", True):
                waking_difficulty = self._get_user_waking_difficulty()

            if session and session.get("puzzle_sessions"):
                session["puzzle_sessions"][-1]["outcome_action"] = "dismissed"
                last_session = session["puzzle_sessions"][-1]
                self.input_handler.thingsboard_client.post({
                    "puzzle_type": last_session.get("puzzle_type"),
                    "puzzle_time_taken_seconds": last_session.get("time_taken_seconds"),
                    "puzzle_is_correct": last_session.get("is_correct"),
                    "puzzle_outcome_action": last_session.get("outcome_action"),
                })

            if session:
                session["waking_difficulty"] = waking_difficulty
                self._complete_sessions[source_alarm_id] = session
                self._pending_sessions.pop(source_alarm_id, None)

            if can_collect_alarm_sessions():
                payload = {
                    "alarm_event": "dismissed",
                    "alarm_id": str(self.current_triggered_alarm.id),
                    "source_alarm_id": source_alarm_id,
                }
                if session and session.get("permissions", {}).get("ask_waking_difficulty", True):
                    payload["waking_difficulty"] = waking_difficulty
                self.input_handler.thingsboard_client.post(payload)

            self.stop_alarm()

        elif choice == "trigger":
            self.trigger_alarm(self.current_triggered_alarm)
        else:
            # Unhandled choice (shouldn't happen), ensure clean-up
            self.stop_alarm()

    def stop_alarm(self):
        """
        Stops the current alarm
        :return:
        """
        if self.state in [AlarmState.TRIGGERED, AlarmState.PUZZLE]:
            logger.debug("Alarm Stopped")
            logger.debug(f"Active alarms: {self.alarms}, {self.snooze_alarms}")

            if self.current_triggered_alarm in self.snooze_alarms:
                self.snooze_alarms.remove(self.current_triggered_alarm)
            self.current_triggered_alarm = None
            self.update()
            self.state = AlarmState.WAITING

    def pull_complete_sessions(self):
        """Return and clear any completed session telemetry batches."""
        sessions = self._complete_sessions
        self._complete_sessions = {}
        return sessions

    def peek_complete_sessions(self):
        """Return a copy of completed sessions without clearing them."""
        return dict(self._complete_sessions)

    def drop_complete_sessions(self, session_ids):
        """Remove session IDs that were successfully uploaded."""
        for session_id in session_ids:
            self._complete_sessions.pop(session_id, None)
