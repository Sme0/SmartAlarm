from time import sleep
from grove_rgb_lcd import *
import grovepi


# ================================
# ==== Code for LCD backlight ====

DISPLAY_RGB_ADDR = 0x30
DISPLAY_TEXT_ADDR = 0x3e

if sys.platform == 'uwp':
    import winrt_smbus as smbus
    bus = smbus.SMBus(1)
else:
    import smbus
    import RPi.GPIO as GPIO
    rev = GPIO.RPI_REVISION
    if rev == 2 or rev == 3:
        bus = smbus.SMBus(1)
    else:
        bus = smbus.SMBus(0)


def setRGB(r, g, b):
    """
    setRGB(r, g, b):
      - Controls the Grove LCD backlight color by writing to the 
        device at DISPLAY_RGB_ADDR.
      - r, g, b range from 0..255 for red, green, and blue channels.
    """
    bus.write_byte_data(DISPLAY_RGB_ADDR, 0x04, 0x15)

    bus.write_byte_data(DISPLAY_RGB_ADDR, 0x06, r)
    bus.write_byte_data(DISPLAY_RGB_ADDR, 0x07, g)
    bus.write_byte_data(DISPLAY_RGB_ADDR, 0x08, b)


def test_lcd ():
    setText("9 x 8 =\n >72<   76")
    setRGB(255, 64, 255)
    
# ==========================



def test_joystick ():

    # set pins
    xpin = 0
    ypin = 1
    grovepi.pinMode(xpin, "INPUT")
    grovepi.pinMode(ypin, "INPUT")

    # main reading loop
    while True:
        try:
            x = grovepi.analogRead(xpin)
            y = grovepi.analogRead(ypin)
            click = 1 if x>= 1020 else 0
        
            print(f"x={x}, y={y}, click={click}")
            sleep(0.5)
        
        except IOError:
            print ("ERROR")
        

def test_button ():
    button = 5
    
    grovepi.pinMode(button, "INPUT")
    
    while True:
        try:
            print(grovepi.digitalRead(button))
            sleep(0.5)
        
        except IOError:
            print("ERROR")
            
def test_buzzer ():
    buzzer = 3
    grovepi.pinMode(buzzer, "OUTPUT")
    
    grovepi.digitalWrite(buzzer, 0)
    sleep(1)
    grovepi.digitalWrite(buzzer, 1)
    sleep(1)
    grovepi.digitalWrite(buzzer, 0)
    
        
if __name__ == "__main__":
    test_buzzer()