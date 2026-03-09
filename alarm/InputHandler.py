from enum import Enum

class InputOption(Enum):
    DISARM = 1
    SNOOZE = 2

class InputHandler:
    def __init__(self):
        # TODO: Initialise pins
        pass

    # TODO: Check inputs and translate to input options
    def check_inputs(self) -> InputOption:
        # placeholder console input
        user_input = input("Enter your input")

        if user_input == "snooze":
            return InputOption.SNOOZE
        if user_input == "disarm":
            return InputOption.DISARM