import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytz

from alarm.alarm_state import AlarmState
from alarm.io.input_handler import InputEventType, InputHandler
from alarm.io.output_handler import DebugOutputHandler, OutputHandler
from alarm.io.pi_bluetooth import BluetoothConfirmation
from alarm.io.temp_sensor import TempSensor
from alarm.puzzles.maths_puzzle import MathsPuzzle
from alarm.puzzles.memory_puzzle import MemoryPuzzle
from alarm.puzzles.puzzle import Puzzle


def _utc_now() -> datetime:
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
            print(
                f"Invalid DEVICE_TIMEZONE '{configured_tz}', falling back to device timezone"
            )

    local_tz = datetime.now().astimezone().tzinfo
    return local_tz or timezone.utc


CLOCK_TIMEZONE = _resolve_clock_timezone()


def _clock_now() -> datetime:
    return datetime.now(CLOCK_TIMEZONE)


def _get_current_day_of_week_number():
    """
    Returns the current day of the week as a number (Monday=0, Sunday=6)
    """
    return _clock_now().weekday()


@dataclass
class Alarm:
    id: str
    time: str
    enabled: bool
    day_of_week: int
    puzzle_type: str
    max_snoozes: int
    snooze_count: int
    source_alarm_id: str


class AlarmController:
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

        self.sensor = TempSensor()

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
                self.output_handler.display_text("   ".join(rendered_options))
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
        # Update current time
        self.current_time = _clock_now().strftime("%H:%M:%S")

    def check_alarms(self) -> bool:
        """
        Checks if there are any alarms due to trigger.
        :return: If an alarm has been triggered
        """
        current_minute = _clock_now().minute
        day_of_week = _get_current_day_of_week_number()

        # Check each alarm and trigger if needed
        alarms_to_check = (self.alarms or []) + (self.snooze_alarms or [])
        for alarm in alarms_to_check:
            if (
                self.state == AlarmState.WAITING
                and day_of_week == alarm.day_of_week
                and self.current_time == (alarm.time + ":00")
            ):
                self.trigger_alarm(alarm)
                return True

        # If there are no alarms triggered
        if (
            self.state == AlarmState.WAITING
            and current_minute != self.last_displayed_minute
        ):
            self.last_displayed_minute = current_minute

            temp, humidity = self.sensor.get_temp_and_humidity()

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
        self._pending_sessions.setdefault(
            source_alarm_id,
            {
                "triggered_at": _utc_now().isoformat(),
                "puzzle_sessions": [],
            },
        )

        self.output_handler.display_text(
            f"Alarm Triggered: {_clock_now().strftime('%H:%M')}"
        )
        self.output_handler.buzzer.play_alarm_sound()
        if isinstance(self.output_handler, DebugOutputHandler):
            print("[DEBUG] Type 'dismiss' to solve puzzle.")

    def run_alarm_interaction(self):

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
        session = self._pending_sessions[source_alarm_id]
        session["puzzle_sessions"].append(puzzle.export_session(source_alarm_id))

        if not solved:
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

        choice = self._decision_selection(options)
        if choice:
            choice = choice.lower()

        if choice == "snooze":
            # TODO: Make snooze time editable through web
            session["puzzle_sessions"][-1]["outcome_action"] = "snoozed"
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
            self.stop_alarm()

        elif choice == "dismiss":
            waking_difficulty = self._get_user_waking_difficulty()
            session["puzzle_sessions"][-1]["outcome_action"] = "dismissed"
            session["waking_difficulty"] = waking_difficulty
            self._complete_sessions[source_alarm_id] = session
            self._pending_sessions.pop(source_alarm_id, None)
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
            print("Alarm Stopped")
            print(f"Active alarms: {self.alarms}, {self.snooze_alarms}")

            if self.current_triggered_alarm in self.snooze_alarms:
                self.snooze_alarms.remove(self.current_triggered_alarm)
            self.current_triggered_alarm = None
            self.update()
            self.state = AlarmState.WAITING

    def pull_complete_sessions(self):
        sessions = self._complete_sessions
        self._complete_sessions = {}
        return sessions

    def peek_complete_sessions(self):
        return dict(self._complete_sessions)

    def drop_complete_sessions(self, session_ids):
        for session_id in session_ids:
            self._complete_sessions.pop(session_id, None)
