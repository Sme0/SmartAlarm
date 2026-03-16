### runs every half second to check the direction of the joystick.
# if different from the most recent direction, then appends to list
# then counts the non-neutral items in the list
# if == 5, returns list of non-neutral directions

import time
import grovepi

def interpretCoords(x, y):
    #up side values
    if x < 385:
        if y < 385:
            if x < y:
                return("UP")
            else:
                return("LEFT")
        elif y > 645:
            if (x-255) < (y-645):
                return("UP")
            else:
                return("RIGHT")
        else:
            return("UP")

    #down side values
    elif x > 645:
        if y < 385:
            if (x-645) < (y-255):
                return("DOWN")
            else:
                return ("LEFT")
        elif y > 645:
            if (x-645) < (y-645):
                return("RIGHT")
            else:
                return("DOWN")
        else:
            return("DOWN")

    #main section for left and right
    elif y < 385:
        return("LEFT")
    elif y > 645:
        return("RIGHT")

    else:
        return("NEUTRAL")

def readDirections(xpin, ypin):
    user_inputs = ["NEUTRAL"]
    direction_values = []
    while True: #len(direction_values) < 5:
        try:
            x = grovepi.analogRead(xpin)
            y = grovepi.analogRead(ypin)
            
            direction = interpretCoords(x, y)

            if direction != user_inputs[len(user_inputs)-1]:
                print(direction)
                user_inputs.append(direction)
            
            direction_values = [item for item in user_inputs if item != "NEUTRAL"]
            time.sleep(0.5)


        except IOError:
            print ("ERROR: Simon Says User Input")

    return (direction_values)