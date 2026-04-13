import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import pytz

from alarm.io.output_handler import OutputHandler
from alarm.io.input_handler import InputHandler
from alarm.alarm_state import AlarmState
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
            print(f"Invalid DEVICE_TIMEZONE '{configured_tz}', falling back to device timezone")

    local_tz = datetime.now().astimezone().tzinfo
    return local_tz or timezone.utc


CLOCK_TIMEZONE = _resolve_clock_timezone()


def _clock_now() -> datetime:
    return datetime.now(CLOCK_TIMEZONE)


def get_current_day_of_week_number():
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

    def __init__(self, input_handler: InputHandler, output_handler: OutputHandler):

        self.input_handler = input_handler
        self.output_handler = output_handler

        # Current time in 24-hour format
        self.current_time = 0
        self.last_displayed_minute = None

        # Alarms in 24-hour format
        self.alarms: List[Alarm] = []
        self.snooze_alarms: List[Alarm] = []

        # Current alarm state
        self.state : AlarmState = AlarmState.WAITING
        self.current_triggered_alarm: Alarm | None = None
        
        # Session data
        self._pending_sessions: Dict[str, Dict[str, Any]] = {}
        self._complete_sessions: Dict[str, Dict[str, Any]] = {}

    def update(self):
        # Update current time
        self.current_time = _clock_now().strftime("%H:%M:%S")


    def check_alarms(self) -> bool:
        """
        Checks if there are any alarms due to trigger.
        :return: If an alarm has been triggered
        """
        current_minute = _clock_now().minute
        day_of_week = get_current_day_of_week_number()

        # Check each alarm and trigger if needed
        for alarm in (self.alarms + self.snooze_alarms):
            if self.state == AlarmState.WAITING and day_of_week == alarm.day_of_week and self.current_time == (alarm.time + ":00"):
                self.trigger_alarm(alarm)
                return True

        # If there are no alarms triggered
        if self.state == AlarmState.WAITING and current_minute != self.last_displayed_minute:
            self.last_displayed_minute = current_minute
            self.output_handler.display_text(_clock_now().strftime('%H:%M'))

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
        self._pending_sessions.setdefault(source_alarm_id, {
            "triggered_at": _utc_now().isoformat(),
            "puzzle_sessions": [],
        })

        self.output_handler.display_text(f"Alarm Triggered: {_clock_now().strftime('%H:%M')}")

    def disarm_alarm(self):
        """
        Disarms the current alarm
        :return:
        """
        if not self.current_triggered_alarm:
            return

        self.state = AlarmState.PUZZLE
        
        # Puzzle startup logic. Use whenever a puzzle is being started
        # TODO: Choose game automatically
        puzzle: Puzzle = MathsPuzzle(self.input_handler, self.output_handler)
        puzzle.run_puzzle()
        source_alarm_id = str(self.current_triggered_alarm.source_alarm_id or self.current_triggered_alarm.id)
        session = self._pending_sessions[source_alarm_id]
        session["puzzle_sessions"].append(puzzle.export_session(source_alarm_id))

        # On alarm completion/disarm
        self._complete_sessions[source_alarm_id] = session
        self._pending_sessions.pop(source_alarm_id, None)
        self.stop_alarm()

    def snooze_alarm(self):
        """
        Snoozes the current alarm by 5 minutes
        :return:
        """
        if not self.current_triggered_alarm:
            return

        max_snoozes = int(self.current_triggered_alarm.max_snoozes)
        if max_snoozes < 0:
            max_snoozes = 0

        current_snooze_count = self.current_triggered_alarm.snooze_count
        if current_snooze_count >= max_snoozes:
            self.output_handler.display_text("Snooze limit reached")
            return

        # Puzzle startup logic. Use whenever a puzzle is being started
        # TODO: Choose game automatically
        puzzle: Puzzle = MathsPuzzle(self.input_handler, self.output_handler)
        puzzle.run_puzzle()
        source_alarm_id = str(self.current_triggered_alarm.source_alarm_id or self.current_triggered_alarm.id)
        session = self._pending_sessions[source_alarm_id]
        session["puzzle_sessions"].append(puzzle.export_session(source_alarm_id))

        # TODO: Make snooze time editable through web
        snooze_time = (_clock_now() + timedelta(minutes=5)).strftime("%H:%M")
        source_alarm_id = self.current_triggered_alarm.source_alarm_id or self.current_triggered_alarm.id
        self.snooze_alarms.append(Alarm(
            id=f"{source_alarm_id}-Snooze-{current_snooze_count + 1}",
            time=snooze_time,
            enabled=True,
            day_of_week=get_current_day_of_week_number(),
            puzzle_type=self.current_triggered_alarm.puzzle_type,
            max_snoozes=max_snoozes,
            snooze_count=current_snooze_count + 1,
            source_alarm_id=source_alarm_id,
        ))
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

