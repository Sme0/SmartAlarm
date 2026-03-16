import random as rand
from joystickDirections import *
from alarmClockDisplay import *
import grovepi

def generatePattern():
    directions = ["UP", "DOWN", "LEFT", "RIGHT"]
    puzzle_length = 5 #maybe change to variable that the user can edit
    instructions = []
    for i in range(0, puzzle_length):
        x = rand.randint(0,3)
        instructions.append(directions[x])
    return instructions

def printInstructions(instructions):
    d = Display()
    
    d.set_text("Memory game: Copy the\norder with the joystick.")

    # create new memory game
    md = MemoryDisplay(instructions)
    
    # format directions for display
    directions = md.format_directions()
    
    # iterate through directions
    for i in directions:
        d.set_text(i)
        sleep(1)
    
    d.set_text(" ")


def simonSays(xpin, ypin):
    #generates the pattern
    instructions = generatePattern()

    #display instructions
    #change to call proper lcd display
    print(instructions)
    printInstructions(instructions)
    
    #takes user input, pulls from joystickDirections
    direction_values = readDirections(xpin,ypin)

    #run comparison
    #if answer correct, return true
    #if answer wrong, return false
    if instructions == direction_values:
        return True
    else:
        return False