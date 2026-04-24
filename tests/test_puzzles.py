"""Puzzle tests: base export behavior plus maths and memory puzzle logic."""

import unittest
from unittest.mock import patch

from tests.bootstrap import stub_optional_device_dependencies


stub_optional_device_dependencies()

from alarm.io.input_handler import InputEventType, InputHandler, JoystickDirection
from alarm.puzzles.maths_puzzle import MathsPuzzle
from alarm.puzzles.memory_puzzle import MemoryPuzzle
from alarm.puzzles.puzzle import Puzzle


class _Tb:
    def post(self, data):
        return None


class _Input(InputHandler):
    def __init__(self):
        super().__init__(_Tb())

    def check_inputs(self, state=None):
        return None


class _Output:
    def __init__(self):
        self.text = []
        self.maths = []
        self.memory = []

    def display_text(self, text):
        self.text.append(text)

    def display_maths_problem(self, question, options, selected_index=0):
        self.maths.append((question, list(options), selected_index))

    def play_memory_sequence(self, sequence):
        self.memory.append(list(sequence))


class SimplePuzzle(Puzzle):
    def prepare_puzzle(self):
        self.problem = "1 + 1"
        self.solution = 2
        self.choices = [1, 2, 3]
        self.current_selection = 1

    def display_puzzle(self):
        return None


class _FeedInput(_Input):
    def __init__(self, event_types):
        super().__init__()
        self.event_types = list(event_types)

    def check_inputs(self, state=None):
        if self.event_types:
            self.push_event(self.event_types.pop(0))


class PuzzleTests(unittest.TestCase):
    def test_base_puzzle_exports_session_data(self):
        """Exported puzzle sessions should include the key fields and timing."""
        puzzle = SimplePuzzle(_Input(), _Output())
        puzzle.prepare_puzzle()
        puzzle.start_time = 10.0
        puzzle.end_time = 14.5

        exported = puzzle.export_session("session-1", outcome_action="dismissed")

        self.assertEqual(exported["alarm_session_id"], "session-1")
        self.assertEqual(exported["puzzle_type"], "simple")
        self.assertEqual(exported["question"], "1 + 1")
        self.assertTrue(exported["is_correct"])
        self.assertEqual(exported["time_taken_seconds"], 4.5)
        self.assertEqual(exported["outcome_action"], "dismissed")

    def test_base_puzzle_times_out_after_two_minutes_without_input(self):
        """Base puzzles should fail after the two-minute timeout without input."""
        output = _Output()
        puzzle = SimplePuzzle(_Input(), output)

        with patch("alarm.puzzles.puzzle.time.time", side_effect=[0.0, 121.0]):
            timed_out = puzzle.run_puzzle()

        self.assertFalse(timed_out)
        self.assertIn("Puzzle timeout", output.text)

    def test_maths_puzzle_formats_problem_and_moves_selection(self):
        """Maths puzzles should format the prompt and move selection correctly."""
        puzzle = MathsPuzzle(_Input(), _Output())

        with patch("alarm.puzzles.maths_puzzle.mg.genById", return_value=(r"6 \cdot 7", "$42"), create=True):
            with patch("alarm.puzzles.maths_puzzle.random.choice", return_value=2):
                with patch("alarm.puzzles.maths_puzzle.random.randint", side_effect=[1, 2, 3]):
                    with patch("alarm.puzzles.maths_puzzle.random.shuffle", side_effect=lambda values: values.reverse()):
                        choices = puzzle.prepare_puzzle()

        self.assertEqual(puzzle.problem, "6 x 7")
        self.assertEqual(puzzle.solution, 42)
        self.assertIn(42, choices)
        self.assertEqual(puzzle.move_selection_right(), 1)
        self.assertEqual(puzzle.move_selection_left(), 0)

    def test_memory_puzzle_prepares_sequence_and_maps_input(self):
        """Memory puzzles should build the sequence and map joystick input."""
        puzzle = MemoryPuzzle(_Input(), _Output(), puzzle_length=3)

        with patch("alarm.puzzles.memory_puzzle.random.choice", side_effect=[
            JoystickDirection.UP,
            JoystickDirection.LEFT,
            JoystickDirection.RIGHT,
        ]):
            instructions = puzzle.prepare_puzzle()

        self.assertEqual(instructions, [
            JoystickDirection.UP,
            JoystickDirection.LEFT,
            JoystickDirection.RIGHT,
        ])
        self.assertEqual(
            puzzle._event_to_direction(InputEventType.JOYSTICK_DOWN),
            JoystickDirection.DOWN,
        )
        self.assertIsNone(puzzle._event_to_direction(InputEventType.JOYSTICK_PRESS))

    def test_memory_puzzle_run_returns_true_for_matching_sequence(self):
        """Matching the memory sequence should solve the puzzle."""
        input_handler = _FeedInput([
            InputEventType.JOYSTICK_UP,
            InputEventType.JOYSTICK_RIGHT,
        ])
        output = _Output()
        puzzle = MemoryPuzzle(input_handler, output, puzzle_length=2)

        with patch.object(puzzle, "prepare_puzzle", side_effect=lambda: setattr(puzzle, "instructions", [
            JoystickDirection.UP,
            JoystickDirection.RIGHT,
        ]) or setattr(puzzle, "solution", [
            JoystickDirection.UP,
            JoystickDirection.RIGHT,
        ]) or setattr(puzzle, "problem", "Memory game")):
            solved = puzzle.run_puzzle()

        self.assertTrue(solved)
        self.assertIn("Correct", output.text)


if __name__ == "__main__":
    unittest.main()
