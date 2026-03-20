from typing import List
from time import sleep
from alarm.io.input_handler import JoystickDirection

try:
    from grove_rgb_lcd import *
    import smbus
except ImportError as e:
    print("Unable to import the following modules. Only an issue if connecting to raspberry pi components")


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

        
def render_maths_question(question: str, options: List[int], selected_index: int = 0) -> str:
    cleaned_options = [str(o).strip(">").strip("<") for o in options]
    if not cleaned_options:
        return f"{question} ="

    selected_index %= len(cleaned_options)
    rendered_options = [f" {o} " for o in cleaned_options]
    rendered_options[selected_index] = f">{cleaned_options[selected_index]}<"
    return f"{question} =\n{''.join(rendered_options)}"


def format_memory_instruction(instruction: JoystickDirection) -> str:
    if instruction == JoystickDirection.UP:
        return f"       {instruction.value}"
    return f"      {instruction.value}"


def format_memory_directions(directions: List[JoystickDirection]) -> List[str]:
    return [format_memory_instruction(d) for d in directions]
        

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
    

    

        