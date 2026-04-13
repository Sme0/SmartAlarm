"""
This module defines a small interface (`OutputHandler`) used by alarm and puzzle
logic to present information without depending on a specific output device.
"""

from abc import ABC, abstractmethod
from typing import List, Any
import time
from alarm.io.displays import Display, render_maths_question, format_memory_directions
from alarm.io.input_handler import JoystickDirection


class OutputHandler(ABC):
    """Interface for presenting alarm and puzzle output to a user-facing display."""

    @abstractmethod
    def display_text(self, text):
        """Display plain text for status updates and simple prompts."""
        raise NotImplementedError

    @abstractmethod
    def display_maths_problem(self, question: str, options: List[int], selected_index: int = 0):
        """
        Display a maths puzzle with selectable options.

        :param question: Puzzle prompt/question text.
        :param options: Candidate numeric answers shown to the user.
        :param selected_index: Currently highlighted option index.
        """
        raise NotImplementedError

    @abstractmethod
    def play_memory_sequence(self, sequence: List[JoystickDirection]):
        """
        Present a memory-game sequence one step at a time.

        The concrete output method depends on implementation (LCD vs console).
        """
        raise NotImplementedError


class RaspberryPiOutputHandler(OutputHandler):
    """Output handler that renders content on the LCD screen."""

    def __init__(self):
        """Initialize display driver wrapper for Raspberry Pi hardware output."""
        self.display = Display()

    def display_text(self, text):
        """Write plain text directly to the LCD."""
        self.display.set_text(text)

    def display_maths_problem(self, question: str, options: List[int], selected_index: int = 0):
        """Render and display a formatted maths question with current selection highlight."""
        self.display.set_text(render_maths_question(question, list(options), selected_index))

    def play_memory_sequence(self, sequence: List[JoystickDirection]):
        """
        Animate memory directions on LCD with brief spacing between steps.
        """
        directions = format_memory_directions(sequence)
        time.sleep(1)
        for direction in directions:
            self.display_text(direction)
            time.sleep(1)
            self.display_text(" ") # Clear screen briefly between directions
            time.sleep(0.2)


class DebugOutputHandler(OutputHandler):
    """Console-based output handler for development/debug environments."""

    def display_text(self, text):
        """Print plain text output with a display prefix for traceability."""
        print(f"[DISPLAY]: {text}")

    def display_maths_problem(self, question: str, options: List[int], selected_index: int = 0):
        """Print a formatted maths puzzle to the terminal."""
        print(f"[MATHS PUZZLE]:\n{render_maths_question(question, options, selected_index)}")

    def play_memory_sequence(self, sequence: List[JoystickDirection]):
        directions = format_memory_directions(sequence)
        time.sleep(1)
        for direction in directions:
            self.display_text(direction)
            time.sleep(1)
            self.display_text(" ")  # Clear screen briefly between directions
            time.sleep(0.2)
