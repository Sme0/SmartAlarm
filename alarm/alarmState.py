from enum import Enum

class AlarmState(Enum):
    WAITING = 1
    TRIGGERED = 2
    SNOOZED = 3