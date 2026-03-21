from memoryGame import *
import grovepi

xpin = 0
ypin = 1
grovepi.pinMode(xpin, "INPUT")
grovepi.pinMode(ypin, "INPUT")

print(simonSays(xpin, ypin))