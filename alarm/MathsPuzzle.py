
import mathgenerator as mg
import random
import Puzzle

class MathsPuzzle (Puzzle):
    def __init__(self):
        super().__init__()

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
        while len(self.choices) < 3:
            offset = random.randint(-10, 10) #could change to scale to solution?
            incorrect_answer = self.solution + offset
            #may have negative numbers
            if incorrect_answer != self.solution and incorrect_answer not in choices:
                self.choices.append(incorrect_answer)
        self.choices.append(int(self.solution))
        random.shuffle(self.choices)
        return self.choices
    
    def display_puzzle(self):
        #use output handler
        #may need to use depending on display?:
        self.solution = int(float(self.solution.replace("$", "")))
        self.problem = self.problem.replace("$", "")
        self.problem = self.problem.replace("\\div", " ÷ ")
        self.problem = self.problem.replace("\\cdot", " × ")
        self.d.set_text(self.md.format_question())

    def check_answer(self, answer):
        return answer == self.solution

            


    
    

