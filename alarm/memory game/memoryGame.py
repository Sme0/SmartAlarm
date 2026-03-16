import random as rand
from joystickDirections import *
import grovepi

def simonSays(xpin, ypin):
    #generates the pattern
    directions = ["UP", "DOWN", "LEFT", "RIGHT"]
    puzzle_length = 5 #maybe change to variable that the user can edit
    instructions = []
    for i in range(0, puzzle_length):
        x = rand.randint(0,3)
        instructions.append(directions[x])

    #display instructions
    #change to call proper lcd display
    print(instructions)
    
    #takes user input, pulls from joystickDirections
    direction_values = readDirections(xpin,ypin)

    #run comparison
    #if answer correct, return true
    #if answer wrong, return false
    if instructions == direction_values:
        return True
    else:
        return False