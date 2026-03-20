from abc import ABC, abstractmethod
from typing import List, Any
import time
from alarm.io.displays import Display, MathsDisplay, MemoryDisplay


class OutputHandler(ABC):

    @abstractmethod
    def display_text(self, text):
        raise NotImplementedError

    @abstractmethod
    def display_maths_problem(self, question: str, options: List[int], selected_index: int = 0):
        raise NotImplementedError

    @abstractmethod
    def maths_move_selection_left(self):
        raise NotImplementedError

    @abstractmethod
    def maths_move_selection_right(self):
        raise NotImplementedError

    @abstractmethod
    def play_memory_sequence(self, sequence: list[str]):
        raise NotImplementedError


class RaspberryPiOutputHandler(OutputHandler):

    def __init__(self):
        self.display = Display()
        self.current_maths_display = None

    def display_text(self, text):
        self.display.set_text(text)

    def display_maths_problem(self, question: str, options: List[int], selected_index: int = 0):
        self.current_maths_display = MathsDisplay(question, options)
        self.current_maths_display.selected_option = selected_index
        self.display.set_text(self.current_maths_display.format_question())

    def maths_move_selection_left(self):
        if self.current_maths_display:
            text = self.current_maths_display.move_selection_left()
            self.display.set_text(text)

    def maths_move_selection_right(self):
        if self.current_maths_display:
            text = self.current_maths_display.move_selection_right()
            self.display.set_text(text)


    def play_memory_sequence(self, sequence: List[Any]):
        md = MemoryDisplay(sequence)
        directions = md.format_directions()

        time.sleep(1)
        
        for direction in directions:
            self.display.set_text(direction)
            time.sleep(1)
            self.display.set_text(" ") # Clear screen briefly between directions
            time.sleep(0.2)


class DebugOutputHandler(OutputHandler):
    def __init__(self):
        self.maths_selected_index = 0
        self.maths_options_count = 4

    def display_text(self, text):
        print(f"[DISPLAY]: {text}")

    def display_maths_problem(self, question: str, options: List[int], selected_index: int = 0):
        self.maths_selected_index = selected_index
        self.maths_options_count = len(options) if options else 4
        # Simulate simple display
        opts_str = " ".join([f">{o}<" if i == selected_index else f" {o} " for i, o in enumerate(options)])
        print(f"[MATHS PUZZLE]: {question} = ?\n{opts_str}")

    def maths_move_selection_left(self):
        self.maths_selected_index = self.maths_selected_index - 1 if self.maths_selected_index < 3 else 0
        print(f"[MATHS PUZZLE]: Selection moved left to {self.maths_selected_index}")

    def maths_move_selection_right(self):
        self.maths_selected_index = self.maths_selected_index + 1 if self.maths_selected_index < 3 else 0
        print(f"[MATHS PUZZLE]: Selection moved right to {self.maths_selected_index}")

    def play_memory_sequence(self, sequence: list[Any]):
        print(f"[MEMORY PUZZLE]: Playing sequence: {[s.value if hasattr(s, 'value') else str(s) for s in sequence]}")
