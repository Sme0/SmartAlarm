from enum import Enum
from grove_rgb_lcd import *
import grovepi




class InputOption(Enum):
    NONE = 0
    DISARM = 1
    SNOOZE = 2

class InputHandler:
    def __init__(self):

        # Current action
        self.current_action = None

        # TODO: Initialise pins numbers
        self.disarm_button = 5

        # TODO: Link pins to button
        grovepi.pinMode(self.disarm_button, "INPUT")

    # TODO: Check inputs and translate to input options
    def check_inputs(self):

        # user_input = input("Enter your input")
        #
        # if user_input == "snooze":
        #     return InputOption.SNOOZE
        # if user_input == "disarm":
        #     return InputOption.DISARM

        self.current_action = InputOption.NONE

        if grovepi.digitalRead(self.disarm_button) == 0:
            self.current_action = InputOption.DISARM

