import time
from abc import ABC, abstractmethod

from joystickDirection import directionRead #will this be part of input handler?
from InputHandler import InputHandler #update after inputhandler finished
from OutputHandler import * #update after outputhandler finished

class Puzzle(ABC):
    def __init__(self, input_handler: InputHandler, output_handler: OutputHandler):
        self.input_handler = input_handler
        self.output_handler = output_handler

        self.problem = None
        self.solution = None

        self.num_snoozes = 0
        self.snooze_cap = 3
        self.time_limit = 120

    @abstractmethod
    def set_puzzle(self): #could add difficulty option
        pass

    @abstractmethod
    def generate_choices(self):
        pass

    @abstractmethod
    def display_puzzle(self, choices):
        pass

    @abstractmethod
    def check_answer(self, answer):
        pass

    def check_snooze_cap(self):
        return self.num_snoozes >= self.snooze_cap

    def run_puzzle(self):
        self.set_puzzle()
        choices = self.generate_choices()
        self.display_puzzle(choices)

        #may need to fix so that timer isn't paused while waiting for input, depends on how inputhandler works
        start_time = time.time()

        while True:
            if time.time() - start_time > self.time_limit:
                #display message on screen: game over? time limit reached?
                return False

            answer = 0 #change 0 to use input handler to get answer from user
            if (self.check_answer(answer)):
                #display message on screen: correct answer
                #self.num_snoozes += 1 <- implement choice of snooze/stop and checking if reached snooze cap
                return True
            else:
                #display message on screen: incorrect
                return False

            #then wait for some time or immediately start again?