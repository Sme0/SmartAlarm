import mathgenerator as mg
import random

from alarm.io.input_handler import InputHandler
from alarm.io.output_handler import OutputHandler
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
        self.current_selection = 0

    def _parse_solution_int(self, raw_solution):
        return int(str(raw_solution).replace("$", "").strip())

    def set_puzzle(self): 
        #generate maths puzzle
        self.problem, self.solution = mg.genById(random.choice(self.puzzle_id))
        self.solution = self._parse_solution_int(self.solution)
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
        self.choices = choices
        return self.choices

    def move_selection_left(self):
        if not self.choices:
            return self.current_selection
        self.current_selection = (self.current_selection - 1) % len(self.choices)
        self.display_puzzle()
        return self.current_selection

    def move_selection_right(self):
        if not self.choices:
            return self.current_selection
        self.current_selection = (self.current_selection + 1) % len(self.choices)
        self.display_puzzle()
        return self.current_selection

    def get_selected_answer(self):
        if not self.choices:
            return None
        return self.choices[self.current_selection]
    
    def display_puzzle(self):
        self.solution = self._parse_solution_int(self.solution)
        self.problem = str(self.problem).replace("$", "")
        self.problem = self.problem.replace("\\div", "÷")
        self.problem = self.problem.replace("\\cdot", "×")
        
        if self.current_selection is None:
            self.current_selection = 0
        self.output_handler.display_maths_problem(self.problem, self.choices, self.current_selection)

    def check_answer(self, answer):
        return answer == self.solution

            


    
    
