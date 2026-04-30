"""Alarm state enum used by the controller state machine."""


from enum import Enum


class AlarmState(Enum):
    """Lifecycle states for the alarm controller."""
    WAITING = 1
    TRIGGERED = 2
    PUZZLE = 3