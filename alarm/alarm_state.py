from enum import Enum


class AlarmState(Enum):
    WAITING = 1
    TRIGGERED = 2
    # TODO: Add playing puzzle state