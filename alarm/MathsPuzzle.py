
import mathgenerator as mg
import random
import time
from abc import ABC, abstractmethod
import Puzzle

from joystickDirection import directionRead #will this be part of input handler?
from InputHandler import InputHandler #update after inputhandler finished
from OutputHandler import * #update after outputhandler finished

class MathsPuzzle (Puzzle):
    def __init__(self, input_handler: InputHandler, output_handler: OutputHandler):
        super().__init__(input_handler, output_handler)

        #types of maths puzzles to select from
        #0 = addition, 1 = subtraction, 2 = multiplication, 3 = division, 11 = basic algebra
        #between 0 and 125

        #to see all:
        #for item in mg.getGenList():
            #print(item[2])
        self.puzzle_id = [0, 1, 2, 3]

    def set_puzzle(self): 
        #generate maths puzzle
        self.problem, self.solution = mg.genById(random.choice(self.puzzle_id))
        self.solution = int(self.solution)
        return self.problem
    
    def generate_choices(self):
        choices = []
        while len(choices) < 3:
            offset = random.randint(-10, 10) #could change to scale to solution?
            incorrect_answer = self.solution + offset
            #may have negative numbers
            if incorrect_answer != self.solution and incorrect_answer not in choices:
                choices.append(incorrect_answer)
        choices.append(int(self.solution))
        random.shuffle(choices)
        return choices
    
    def display_puzzle(self, choices):
        #use output handler
        #may need to use depending on display?:
        #self.solution = int(float(self.solution.replace("$", "")))
        #self.problem = self.problem.replace("$", "")
        #self.problem = self.problem.replace("\\div", " ÷ ")
        #self.problem = self.problem.replace("\\cdot", " × ")
        pass

    def check_answer(self, answer):
        return answer == self.solution

            


    
    

