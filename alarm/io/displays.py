import logging
from typing import List
from time import sleep
from alarm.io.input_handler import JoystickDirection

logger = logging.getLogger(__name__)

# To avoid errors when not running on a Raspberry Pi
try:
    from grove_rgb_lcd import *
except ImportError as e:
    smbus = None
    logger.warning("Unable to import the following modules. Only an issue if connecting to raspberry pi components")


class Display:
    """
    Class to control the Raspberry Pi LCD screen.
    """
    def __init__ (self, rgb_values: List[int] = None, text: str = "") -> None:
        self.colour = rgb_values or [255, 255, 255]
        self.text = text
        
        # initialise memory addresses
        self.DISPLAY_RGB_ADDR = 0x30
        self.DISPLAY_TEXT_ADDR = 0x3e
        self.bus = smbus.SMBus(1)

        self._update_colour()
        self._update_text()

    # sets backlight colour
    def set_colour (self, rgb_values: List[int]) -> None:
        """
        Sets the backlight colour on the LCD display
        :param rgb_values:
        :return:
        """
        self.colour = rgb_values
        self._update_colour()
        
    # writes rgb values to display memory
    def _update_colour (self) -> None:
        """
        Internal method to update the backlight colour on the LCD display
        :return:
        """
        self.bus.write_byte_data(self.DISPLAY_RGB_ADDR, 0x04, 0x15)

        self.bus.write_byte_data(self.DISPLAY_RGB_ADDR, 0x06, self.colour[0])
        self.bus.write_byte_data(self.DISPLAY_RGB_ADDR, 0x07, self.colour[1])
        self.bus.write_byte_data(self.DISPLAY_RGB_ADDR, 0x08, self.colour[2])
        
    # sets displayed text
    def set_text (self, text: str) -> None:
        """
        Sets the text displayed on the LCD display
        :param text:
        :return:
        """
        self.text = text
        self._update_text()
        
    def _update_text (self) -> None:
        """
        Internal method to update the text displayed on the LCD display
        :return:
        """
        setText(self.text)

        
def render_maths_question(question: str, options: List[int], selected_index: int = 0) -> str:
    """
    Renders a maths question to be displayed on a `Display`
    :param question: Question to be formatted
    :param options: Options to be formatted
    :param selected_index: Index of the option that is currently selected
    :return: The formatted/rendered maths question
    """
    cleaned_options = [str(o).strip(">").strip("<") for o in options]
    if not cleaned_options:
        return f"{question} ="

    selected_index %= len(cleaned_options)
    rendered_options = [f" {o} " for o in cleaned_options]
    rendered_options[selected_index] = f">{cleaned_options[selected_index]}<"
    return f"{question} =\n{''.join(rendered_options)}"


def format_memory_instruction(instruction: JoystickDirection) -> str:
    """
    Formats a joystick direction for the Raspberry Pi's LCD screen
    :param instruction: Joystick direction to be formatted
    :return:  value
    """
    if instruction == JoystickDirection.UP:
        return f"       {instruction.value}"
    return f"      {instruction.value}"


def format_memory_directions(directions: List[JoystickDirection]) -> List[str]:
    """
    Helper method, formats each joystick direction
    :param directions: List of joystick directions to be formatted
    :return: List of formatted directions
    """
    return [format_memory_instruction(d) for d in directions]
        
# For debugging, will go once puzzles are fully integrated into the alarm
def maths_sample_code():
    # create new display object
    d = Display()
    
    # format question with the currently selected option
    selected_index = 0
    options = [22, 30, 28, 25]
    d.set_text(render_maths_question("4 x 7", options, selected_index))
    sleep(1)
    
    # move selection left or right
    selected_index = (selected_index - 1) % len(options)
    d.set_text(render_maths_question("4 x 7", options, selected_index))
    sleep(1)
    selected_index = (selected_index + 1) % len(options)
    d.set_text(render_maths_question("4 x 7", options, selected_index))
    sleep(1)
    
    # set display colour to red
    d.set_colour([255, 0, 0])
    
# For debugging, will go once puzzles are fully integrated into the alarm
def simon_sample_code ():
    # create new display object
    d = Display()
    
    directions = format_memory_directions([
        JoystickDirection.LEFT,
        JoystickDirection.RIGHT,
        JoystickDirection.UP,
        JoystickDirection.DOWN,
    ])
    
    # iterate through directions
    for i in directions:
        d.set_text(i)
        sleep(1)


if __name__ == "__main__":
    simon_sample_code()
    

    

        