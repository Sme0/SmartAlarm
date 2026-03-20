import mathgenerator as mg
import random

from alarm.io.input_handler import InputHandler #update after inputhandler finished
from alarm.io.output_handler import * #update after outputhandler finished
from alarm.puzzles.puzzle import Puzzle


class MathsPuzzle(Puzzle):
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
        #generate incorrect options for answer
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
    
    def display_puzzle(self, choices, selected_index=0):

        self.solution = int(str(self.solution).replace("$", ""))
        self.problem = str(self.problem).replace("$", "")
        self.problem = self.problem.replace("\\div", "÷")
        self.problem = self.problem.replace("\\cdot", "×")
        
        self.output_handler.display_maths_problem(self.problem, choices, selected_index)

    def check_answer(self, answer):
        return answer == self.solution

            


    
    
