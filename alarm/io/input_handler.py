import time
from abc import abstractmethod, ABC
from enum import Enum

try:
    from grove_rgb_lcd import *
    import grovepi
except ImportError:
    print("Unable to import Pi libraries")


class InputOption(Enum):
    NONE = 0
    DISARM = 1
    SNOOZE = 2

class JoystickDirection(Enum):
    NEUTRAL = "NEUTRAL"
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

class InputHandler(ABC):
    def __init__(self):
        self.current_action = None

    @abstractmethod
    def check_inputs(self):
        pass


class DebugInputHandler(InputHandler):

    def __init__(self):
        super().__init__()

    def check_inputs(self):

        user_input = input("Enter your input")

        if user_input == "snooze":
            return InputOption.SNOOZE
        if user_input == "disarm":
            return InputOption.DISARM


class RaspberryPiInputHandler(InputHandler):
    def __init__(self):
        super().__init__()

        # Initialise pins
        self.disarm_button = 5
        self.joystick_x = 0
        self.joystick_y = 1

        # Links pins to button
        grovepi.pinMode(self.disarm_button, "INPUT")
        grovepi.pinMode(self.joystick_x, "INPUT")
        grovepi.pinMode(self.joystick_y, "INPUT")

    def check_inputs(self):

        self.current_action = InputOption.NONE
        try:
            if grovepi.digitalRead(self.disarm_button) == 0:
                self.current_action = InputOption.DISARM
        except IOError:
            print("Error")

    def read_joystick(self):
        """
        Collects the x and y coordinates of a joystick input and translates it into
        a JoystickDirection.
        :return: The JoystickDirection for the given x and y
        """
        try:
            x = grovepi.analogRead(self.joystick_x)
            y = grovepi.analogRead(self.joystick_y)
        except IOError:
            print("ERROR: Error reading from joystick")

        # up side values
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

        # down side values
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

    #TODO: Change name
    def read_directions(self, number_of_inputs: int) -> list[JoystickDirection]:
        """
        Collects a number of joy stick inputs that are different to the previous input.
        Does not include neutral joystick inputs in final result
        :param number_of_inputs: The number of non-neutral joystick inputs to collect
        :return: A list of non-neutral joystick inputs made by the user
        """
        user_inputs = [JoystickDirection.NEUTRAL]
        direction_values = []
        while len(direction_values) < number_of_inputs:
            try:

                direction = self.read_joystick()

                if direction != user_inputs[len(user_inputs) - 1]:
                    print(direction)
                    user_inputs.append(direction)

                direction_values = [item for item in user_inputs if item != JoystickDirection.NEUTRAL]
                time.sleep(0.1)


            except IOError:
                print("ERROR: Simon Says User Input")

        return direction_values




