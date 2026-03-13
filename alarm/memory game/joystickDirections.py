### runs every half second to check the direction of the joystick.
# if different from the most recent direction, then appends to list
# then counts the non-neutral items in the list
# if == 5, returns list of non-neutral directions

import time

def interpretCoords(x, y):
    #left side values
    if x < 256:
        if y < 256:
            if x < y:
                return("LEFT")
            else:
                return("UP")
        elif y > 768:
            if x < (1023- y):
                return("LEFT")
            else:
                return("DOWN")
        else:
            return("LEFT")

    #right side values
    elif x > 768:
        if y < 256:
            if (1023- x) < y:
                return("RIGHT")
            else:
                return ("UP")
        elif y > 768:
            if (1023- x) < (1023- y):
                return("RIGHT")
            else:
                return("DOWN")
        else:
            return("RIGHT")

    #main section for up and down
    elif y < 256:
        return("UP")
    elif y > 768:
        return("DOWN")

    else:
        return("NEUTRAL")

def readDirections(xpin, ypin):
    user_inputs = ["NEUTRAL"]
    direction_values = []
    while len(direction_values) < 5:
        try:
            x = grovepi.analogRead(xpin)
            y = grovepi.analogRead(ypin)
            
            direction = interpretCoords(x, y)

            if direction != user_inputs[len(user_inputs)-1]:
                user_inputs.append(direction)
            
            direction_values = [item for item in user_inputs if item != "NEUTRAL"]
            time.sleep(0.5)


        except IOError:
            print ("ERROR: Simon Says User Input")

    return (direction_values)