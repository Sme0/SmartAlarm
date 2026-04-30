"""Memory puzzle implementation that replays joystick direction sequences."""

import random
import time
from typing import List

from alarm.io.input_handler import InputEventType, JoystickDirection
from alarm.puzzles.puzzle import Puzzle


class MemoryPuzzle(Puzzle):
    """Simon-style memory game using joystick direction sequences."""

    def __init__(self, input_handler, output_handler, puzzle_length: int = 5):
        super().__init__(input_handler, output_handler)
        self.puzzle_length = puzzle_length
        self.instructions: List[JoystickDirection] = []
        self.direction_values: List[JoystickDirection] = []

    def generatePattern(self):
        """Generate a random sequence of joystick directions."""
        directions = [
            JoystickDirection.UP,
            JoystickDirection.DOWN,
            JoystickDirection.LEFT,
            JoystickDirection.RIGHT,
        ]
        instructions = []
        for _ in range(self.puzzle_length):
            instructions.append(random.choice(directions))
        return instructions

    def prepare_puzzle(self):
        """Create a new sequence and reset any prior player input."""
        self.instructions = self.generatePattern()
        self.solution = list(self.instructions)
        self.problem = "Memory game: Copy the order with the joystick."
        self.direction_values = []
        return self.instructions

    def display_puzzle(self):
        """Render the instructions by playing the sequence on the display."""
        self.output_handler.display_text("  Memory Game")
        self.output_handler.play_memory_sequence(self.instructions)

    def _event_to_direction(self, event_type: InputEventType):
        """Map a joystick event into a direction value, if applicable."""
        mapping = {
            InputEventType.JOYSTICK_UP: JoystickDirection.UP,
            InputEventType.JOYSTICK_DOWN: JoystickDirection.DOWN,
            InputEventType.JOYSTICK_LEFT: JoystickDirection.LEFT,
            InputEventType.JOYSTICK_RIGHT: JoystickDirection.RIGHT,
        }
        return mapping.get(event_type)

    def get_user_answer(self):
        """Return the sequence entered by the player."""
        return self.direction_values

    def run_puzzle(self):
        """Override the base loop to compare after a full input sequence."""
        self.prepare_puzzle()
        self.display_puzzle()

        # Clear stale movement events from before puzzle start.
        self.input_handler.pop_events_by_type(
            {
                InputEventType.JOYSTICK_LEFT,
                InputEventType.JOYSTICK_RIGHT,
                InputEventType.JOYSTICK_UP,
                InputEventType.JOYSTICK_DOWN,
                InputEventType.JOYSTICK_PRESS,
            }
        )

        self.start_time = time.time()
        while True:
            if time.time() - self.start_time > self.time_limit:
                self.end_time = time.time()
                self.output_handler.display_text("Puzzle timeout")
                return False

            self.input_handler.check_inputs()
            events = self.input_handler.pop_events_by_type(
                {
                    InputEventType.JOYSTICK_LEFT,
                    InputEventType.JOYSTICK_RIGHT,
                    InputEventType.JOYSTICK_UP,
                    InputEventType.JOYSTICK_DOWN,
                }
            )

            if not events:
                time.sleep(0.05)
                continue

            for event in events:
                direction = self._event_to_direction(event.event_type)
                if direction is None:
                    continue

                self.direction_values.append(direction)

                # Original flow: compare after collecting the full sequence.
                if (
                    len(self.direction_values) >= len(self.instructions)
                    or event.event_type == InputEventType.JOYSTICK_PRESS
                ):
                    self.end_time = time.time()
                    if self.check_answer():
                        self.output_handler.display_text("Correct")
                        return True

                    self.output_handler.display_text("Incorrect")
                    return False
