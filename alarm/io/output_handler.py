from abc import ABC, abstractmethod
from typing import List, Any
import time
from alarm.io.displays import Display, render_maths_question, format_memory_directions


class OutputHandler(ABC):

    @abstractmethod
    def display_text(self, text):
        raise NotImplementedError

    @abstractmethod
    def display_maths_problem(self, question: str, options: List[int], selected_index: int = 0):
        raise NotImplementedError

    @abstractmethod
    def play_memory_sequence(self, sequence: list[str]):
        raise NotImplementedError


class RaspberryPiOutputHandler(OutputHandler):

    def __init__(self):
        self.display = Display()

    def display_text(self, text):
        self.display.set_text(text)

    def display_maths_problem(self, question: str, options: List[int], selected_index: int = 0):
        self.display.set_text(render_maths_question(question, list(options), selected_index))


    def play_memory_sequence(self, sequence: List[Any]):
        directions = format_memory_directions(sequence)

        time.sleep(1)
        
        for direction in directions:
            self.display.set_text(direction)
            time.sleep(1)
            self.display.set_text(" ") # Clear screen briefly between directions
            time.sleep(0.2)


class DebugOutputHandler(OutputHandler):
    def display_text(self, text):
        print(f"[DISPLAY]: {text}")

    def display_maths_problem(self, question: str, options: List[int], selected_index: int = 0):
        print(f"[MATHS PUZZLE]:\n{render_maths_question(question, options, selected_index)}")

    def play_memory_sequence(self, sequence: list[Any]):
        print(f"[MEMORY PUZZLE]: Playing sequence: {[s.value if hasattr(s, 'value') else str(s) for s in sequence]}")
