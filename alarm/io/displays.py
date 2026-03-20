from typing import List
from time import sleep
from input_handler import JoystickDirection

try:
    from grove_rgb_lcd import *
    import smbus
except ImportError as e:
    print("Unable to import the following modules. Only an issue if connecting to raspberry pi components" + e)


class Display:
    def __init__ (self, rgb_values: List[int] = [255, 255, 255], text: str = "") -> None:
        self.colour = rgb_values
        self.text = text
        
        # initialise memory addresses
        self.DISPLAY_RGB_ADDR = 0x30
        self.DISPLAY_TEXT_ADDR = 0x3e
        self.bus = smbus.SMBus(1)
        
        self.update_colour()
        self.update_text()

    # sets backlight colour
    def set_colour (self, rgb_values: List[int]) -> None:
        self.colour = rgb_values
        self.update_colour()
        
    # writes rgb values to display memory
    def update_colour (self) -> None:
        self.bus.write_byte_data(self.DISPLAY_RGB_ADDR, 0x04, 0x15)

        self.bus.write_byte_data(self.DISPLAY_RGB_ADDR, 0x06, self.colour[0])
        self.bus.write_byte_data(self.DISPLAY_RGB_ADDR, 0x07, self.colour[1])
        self.bus.write_byte_data(self.DISPLAY_RGB_ADDR, 0x08, self.colour[2])
        
    # sets displayed text
    def set_text (self, text: str) -> None:
        self.text = text
        self.update_text()
        
    def update_text (self) -> None:
        setText(self.text)
        
        
        
class MathsDisplay:
    def __init__(self, question: str, options: List[int]) -> None:
        self.question = question
        self.options = options
        self.selected_option = 0
        
    # convert self.questions and self.options into string formatted for screen
    def format_question(self) -> str:
        displayed_options = self.update_selection([str(o) for o in self.options])
        unpacked_options = f"{displayed_options[0]}{displayed_options[1]}{displayed_options[2]}{displayed_options[3]}"
        
        question = f"{self.question} =\n{unpacked_options}"
        return question
    
    # clear current selection and add for different option
    def update_selection(self, options: List[str]) -> List[str]:
        updated_options = []
        for o in options:
            cleared_option = o.strip(">").strip("<")
            updated_options.append(f" {cleared_option} ")
        updated_options[self.selected_option] = f">{options[self.selected_option]}<"
        return updated_options
    
    # selects option to left of current selection; can loop around
    def move_selection_left(self) -> str:
        self.selected_option = self.selected_option - 1 if self.selected_option > 1 else 3
        return self.format_question()
    
    # selections option to right of current selection; can loop around
    def move_selection_right(self) -> str:
        self.selected_option = self.selected_option + 1 if self.selected_option < 3 else 0
        return self.format_question()
    
    # get currently selected option
    def current_selection(self) -> int:
        return self.selected_option


class MemoryDisplay:
    def __init__ (self, directions: List[JoystickDirection]) -> None:
        self.directions = directions
        
    def format_directions(self) -> List[str]:
        return [self.format_single_instruction(d) for d in self.directions]
        
    
    def format_single_instruction(self, instruction: JoystickDirection):
        if instruction == JoystickDirection.UP:
            return f"       {instruction.value}"
        else:
            return f"      {instruction.value}"
        

def maths_sample_code():
    # create new display object
    d = Display()
    
    # create new MathsDisplay object for new question
    md = MathsDisplay("4 x 7", [22, 30, 28, 25])
    d.set_text(md.format_question())
    sleep(1)
    
    # move selection left or right
    d.set_text(md.move_selection_left())
    sleep(1)
    d.set_text(md.move_selection_right())
    sleep(1)
    
    # set display colour to red
    d.set_colour([255, 0, 0])
    

def simon_sample_code ():
    # create new display object
    d = Display()
    
    # create new memory game
    md = MemoryDisplay([JoystickDirection.LEFT, JoystickDirection.RIGHT, JoystickDirection.UP, JoystickDirection.DOWN])
    
    # format directions for display
    directions = md.format_directions()
    
    # iterate through directions
    for i in directions:
        d.set_text(i)
        sleep(1)


if __name__ == "__main__":
    simon_sample_code()
    

    

        