"""
Input handling for both debug and Raspberry Pi modes.

Design summary:
- Input providers call `push_event(...)` to enqueue typed input events.
- Consumers (alarm loop, puzzles) call `pop_events...(...)` to drain events.
"""

import time
from abc import abstractmethod, ABC
from collections import deque
from dataclasses import dataclass
from enum import Enum
import select
import sys
from typing import List, Set

from alarm.alarm_state import AlarmState
from alarm.io.grovepi_lock import grovepi_lock
from alarm.thingsboard_client import ThingsBoardClient

try:
    import msvcrt # Windows-only, used for non-blocking console input in debug mode
except ImportError:
    msvcrt = None

# To avoid import errors when not run on the Raspberry Pi
try:
    from grove_rgb_lcd import *
    import grovepi
except ImportError:
    print("Unable to import Pi libraries. Only an issue if connecting to raspberry pi components.")


class InputEventType(Enum):
    """
    Event type to classify different events based on physical input from
    the InputHandler.
    """

    ALARM_DISMISS = "ALARM_DISMISS"
    ALARM_SNOOZE = "ALARM_SNOOZE"
    JOYSTICK_LEFT = "JOYSTICK_LEFT"
    JOYSTICK_RIGHT = "JOYSTICK_RIGHT"
    JOYSTICK_UP = "JOYSTICK_UP"
    JOYSTICK_DOWN = "JOYSTICK_DOWN"
    JOYSTICK_PRESS = "JOYSTICK_PRESS"

class JoystickDirection(Enum):
    """Normalized joystick direction states from analogue stick coordinates."""

    NEUTRAL = "NEUTRAL"
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    PRESS = "PRESS"


@dataclass
class InputEvent:
    """Single input event captured by an `InputHandler` implementation."""

    event_type: InputEventType
    timestamp: float
    payload: object = None

class InputHandler(ABC):
    """
    Abstract input source with a bounded in-memory event queue.

    Subclasses should implement `check_inputs(...)` to poll their input source and
    call `push_event(...)` whenever a meaningful input action occurs.
    """

    def __init__(self, thingsboard_client: ThingsBoardClient, max_events: int = 128):
        """
        Create a handler with a bounded queue.

        :param thingsboard_client: ThingsBoard client to use
        :param max_events: Maximum number of queued events retained. If the queue
            fills, oldest events are dropped automatically by `deque(maxlen=...)`.
        """
        self.thingsboard_client = thingsboard_client
        self._events = deque(maxlen=max_events)

    @abstractmethod
    def check_inputs(self, state: AlarmState=None):
        """
        Poll the input source once and enqueue any detected actions.

        Implementations should be quick/non-blocking where possible so the main
        alarm loop stays responsive.
        """
        pass

    def push_event(self, event_type: InputEventType, payload: object = None):
        """
        Enqueue a normalized input event.
        """
        event = InputEvent(event_type=event_type, timestamp=time.time(), payload=payload)
        print("Recognised: " + event.event_type.__str__())
        self._events.append(event)
        self.thingsboard_client.post({
            "input_event": event.event_type.__str__(),
            "input_timestamp": event.timestamp,
        })

    def pop_events(self) -> List[InputEvent]:
        """Return and clear all queued events (FIFO order)."""
        events = list(self._events)
        self._events.clear()
        return events

    def pop_events_by_type(self, event_types: Set[InputEventType]) -> List[InputEvent]:
        """
        Return only events whose type is in `event_types`.

        Non-matching events remain queued for other consumers.
        """
        matching = []
        remaining = deque(maxlen=self._events.maxlen)
        while self._events:
            event = self._events.popleft()
            if event.event_type in event_types:
                matching.append(event)
            else:
                remaining.append(event)
        self._events = remaining
        return matching

    def _puzzle_event_from_direction(self, direction: JoystickDirection):
        """Map a joystick direction into the corresponding puzzle event type."""
        mapping = {
            JoystickDirection.LEFT: InputEventType.JOYSTICK_LEFT,
            JoystickDirection.RIGHT: InputEventType.JOYSTICK_RIGHT,
            JoystickDirection.UP: InputEventType.JOYSTICK_UP,
            JoystickDirection.DOWN: InputEventType.JOYSTICK_DOWN,
            JoystickDirection.PRESS: InputEventType.JOYSTICK_PRESS,
        }
        return mapping.get(direction)


class DebugInputHandler(InputHandler):
    """
    Keyboard-driven input handler for local/debug runs.

    Commands are read from stdin and translated into queued `InputEvent`s.
    """

    def __init__(self, thingsboard_client: ThingsBoardClient):
        """Initialise command-to-event mapping for debug mode."""
        super().__init__(thingsboard_client)
        self._line_buffer = ""

        self._command_map = {
            "snooze": InputEventType.ALARM_SNOOZE,
            "dismiss": InputEventType.ALARM_DISMISS,
            "left": InputEventType.JOYSTICK_LEFT,
            "right": InputEventType.JOYSTICK_RIGHT,
            "up": InputEventType.JOYSTICK_UP,
            "down": InputEventType.JOYSTICK_DOWN,
            "joy_press": InputEventType.JOYSTICK_PRESS,
        }

    def _read_non_blocking_command(self):
        """
        Read one line from stdin without blocking the main loop.

        :return: Lower-cased command string, or None if no input is available.
        """
        if msvcrt is not None:
            return self._read_non_blocking_command_windows()

        # select keeps debug mode responsive by avoiding blocking input().
        try:
            has_input = select.select([sys.stdin], [], [], 0)[0]
        except (ValueError, OSError):
            return None
        if not has_input:
            return None

        line = sys.stdin.readline()
        if not line:
            return None
        return line.strip().lower()

    def _read_non_blocking_command_windows(self):
        """
        Windows-friendly line reader for terminals where select(stdin) is unreliable.
        Collects typed characters until Enter is pressed, then returns one command.
        """
        if msvcrt is None:
            return None

        while msvcrt.kbhit():
            char = msvcrt.getwch()

            if char in ("\r", "\n"):
                command = self._line_buffer.strip().lower()
                self._line_buffer = ""
                if command:
                    print("")
                    return command
                print("")
                return None

            if char == "\003":
                raise KeyboardInterrupt

            if char == "\b":
                if self._line_buffer:
                    self._line_buffer = self._line_buffer[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue

            # Special keys (arrows...) -> skip their second byte and ignore
            if char in ("\x00", "\xe0"):
                if msvcrt.kbhit():
                    msvcrt.getwch()
                continue

            self._line_buffer += char
            sys.stdout.write(char)
            sys.stdout.flush()

        return None

    def check_inputs(self, state: AlarmState=None):
        """
        Poll console for user input once and enqueue a matching event if present.

        Unknown commands are ignored to keep the loop tolerant while testing.
        """
        # In WAITING mode we still poll so buffered newline input does not build up.
        command = self._read_non_blocking_command()
        if not command:
            return

        event_type = self._command_map.get(command)
        if event_type is not None:
            self.push_event(event_type)


class RaspberryPiInputHandler(InputHandler):
    """
    Hardware input handler for Raspberry Pi + Grove components.

    Captures button presses and joystick movement, applies edge detection and
    debounce, and emits normalised input events.
    """

    def __init__(self, thingsboard_client: ThingsBoardClient):
        """Initialise GPIO pin mappings, hardware state cache, and debounce config."""
        super().__init__(thingsboard_client)

        if grovepi is None:
            raise RuntimeError("RaspberryPiInputHandler requires grovepi to be installed and importable.")

        # Initialise pins
        self.dismiss_button = 4
        self.joystick_x = 0
        self.joystick_y = 1

        # Links pins to button
        with grovepi_lock:
            grovepi.pinMode(self.dismiss_button, "INPUT")
            grovepi.pinMode(self.joystick_x, "INPUT")
            grovepi.pinMode(self.joystick_y, "INPUT")

        self.last_dismiss_button_state = 1
        self.last_joystick_direction = JoystickDirection.NEUTRAL
        self.last_event_time = {}
        self.debounce_seconds = 0.18

    def _is_debounced(self, event_type: InputEventType):
        """
        Check whether an event type is allowed based on how quickly two of the same event
        happened to each other.

        :return: True if enough time has elapsed since last accepted event.
        """
        now = time.time()
        previous = self.last_event_time.get(event_type, 0)
        if now - previous < self.debounce_seconds:
            return False
        self.last_event_time[event_type] = now
        return True

    def check_inputs(self, state: AlarmState=None):
        """
        Poll hardware once and enqueue button/joystick events.

        - Dismiss button uses edge-triggering (transition to pressed).
        - Joystick emits events only on direction changes.
        - Debounce guards against repeated noise/bounce events.
        """
        try:
            with grovepi_lock:
                dismiss_button_state = grovepi.digitalRead(self.dismiss_button)

            # Trigger once when button transitions from not pressed -> pressed.
            if dismiss_button_state == 0 and self.last_dismiss_button_state != 0:
                if self._is_debounced(InputEventType.ALARM_DISMISS):
                    self.push_event(InputEventType.ALARM_DISMISS)

            self.last_dismiss_button_state = dismiss_button_state

            direction = self.read_joystick()
            if direction is not None and direction != self.last_joystick_direction:
                self.last_joystick_direction = direction
                event_type = self._puzzle_event_from_direction(direction)
                if event_type is not None and self._is_debounced(event_type):
                    self.push_event(event_type)
        except IOError:
            print("Error")

    def read_joystick(self):
        """
        Collects the x and y coordinates of a joystick input and translates it into
        a JoystickDirection.

        Threshold ranges are tuned around a neutral centre and map quadrants to
        cardinal directions.

        :return: The JoystickDirection for the given x and y
        """
        try:
            with grovepi_lock:
                x = grovepi.analogRead(self.joystick_x)
                y = grovepi.analogRead(self.joystick_y)
        except IOError:
            print("ERROR: Error reading from joystick")
            return JoystickDirection.NEUTRAL

        # Joystick press
        if x > 1020:
            return JoystickDirection.PRESS

        # upside values
        if x < 385:
            if y < 385:
                if x < y:
                    return JoystickDirection.UP
                else:
                    return JoystickDirection.LEFT
            elif y > 645:
                if (x - 255) < (y - 645):
                    return JoystickDirection.UP
                else:
                    return JoystickDirection.RIGHT
            else:
                return JoystickDirection.UP

        # downside values
        elif x > 645:
            if y < 385:
                if (x - 645) < (y - 255):
                    return JoystickDirection.DOWN
                else:
                    return JoystickDirection.LEFT
            elif y > 645:
                if (x - 645) < (y - 645):
                    return JoystickDirection.RIGHT
                else:
                    return JoystickDirection.DOWN
            else:
                return JoystickDirection.DOWN

        # main section for left and right
        elif y < 385:
            return JoystickDirection.LEFT
        elif y > 645:
            return JoystickDirection.RIGHT

        else:
            return JoystickDirection.NEUTRAL
