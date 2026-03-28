from abc import ABC, abstractmethod
import time

from alarm.io.input_handler import InputHandler, InputEventType
from alarm.io.output_handler import OutputHandler

class Puzzle(ABC):
    def __init__(self, input_handler: InputHandler, output_handler: OutputHandler):
        self.input_handler = input_handler
        self.output_handler = output_handler

        # The question and the required answer for the puzzle
        self.problem = None
        self.solution = None

        # Choices that the user can choose from. Depending on puzzle may not be used
        self.choices = None

        # For puzzles that require selecting from a set of choices
        self.current_selection = None

        #TODO: Move snooze logic to AlarmController
        self.num_snoozes = 0
        self.snooze_cap = 3

        self.start_time = None
        self.end_time = None
        self.time_limit = 120



    @abstractmethod
    def prepare_puzzle(self): #could add difficulty option
        """
        Prepares the puzzle's question and potential possible answers
        :return:
        """
        pass

    @abstractmethod
    def display_puzzle(self):
        """
        Displays the puzzle to the output handler.
        :return:
        """
        pass

    def check_answer(self) -> bool:
        """
        Checks answer and returns the result. May be overridden if logic for a specific puzzle
        is different.
        :return: The result
        """
        return self.get_user_answer() == self.solution

    def on_joystick_left(self):
        """
        Handles joystick_left input
        :return:
        """
        return

    def on_joystick_right(self):
        """
        Handles joystick_right input
        :return:
        """
        return

    def on_joystick_up(self):
        """
        Handles joystick_up input
        :return:
        """
        return

    def on_joystick_down(self):
        """
        Handles joystick_down input
        :return:
        """
        return

    def get_user_answer(self):
        """
        By default, retrieves the currently selected answer. Must be overridden for puzzles that do
        not use selection as their mean of retrieving the user's answer.
        :return: The user's answer
        """
        if not self.choices:
            return None
        return self.choices[self.current_selection]

    def handle_puzzle_event(self, event_type: InputEventType):
        """
        Translates an `InputEventType` into an action for the puzzle. Modify
        actions in
        :param event_type:
        :return:
        """
        if event_type == InputEventType.JOYSTICK_LEFT:
            self.on_joystick_left()
            self.display_puzzle()
        elif event_type == InputEventType.JOYSTICK_RIGHT:
            self.on_joystick_right()
            self.display_puzzle()
        elif event_type == InputEventType.JOYSTICK_UP:
            self.on_joystick_up()
            self.display_puzzle()
        elif event_type == InputEventType.JOYSTICK_DOWN:
            self.on_joystick_down()
            self.display_puzzle()

    #TODO: Move to AlarmController
    def check_snooze_cap(self):
        return self.num_snoozes >= self.snooze_cap

    def run_puzzle(self):
        """
        Default method to run a puzzle. May be overridden if logic for a specific puzzle is different
        :return:
        """
        #create and display question and possible answers (if applicable)
        self.prepare_puzzle()
        self.display_puzzle()

        #may need to fix so that timer isn't paused while waiting for input, depends on how inputhandler works
        self.start_time = time.time()

        # Poll input events until timeout and only submit when a submit event arrives.
        while True:
            if time.time() - self.start_time > self.time_limit:
                self.output_handler.display_text("Puzzle timeout")
                return False

            self.input_handler.check_inputs()
            events = self.input_handler.pop_events_by_type({
                InputEventType.JOYSTICK_LEFT,
                InputEventType.JOYSTICK_RIGHT,
                InputEventType.JOYSTICK_UP,
                InputEventType.JOYSTICK_DOWN,
                InputEventType.JOYSTICK_PRESS,
            })

            if not events:
                time.sleep(0.05)
                continue

            for event in events:

                if event.event_type == InputEventType.JOYSTICK_PRESS:
                    self.end_time = time.time()
                    if self.check_answer():
                        self.output_handler.display_text("Correct")
                        return True

                    self.output_handler.display_text("Incorrect")
                    return False

                self.handle_puzzle_event(event.event_type)
