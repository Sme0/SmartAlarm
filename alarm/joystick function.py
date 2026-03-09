def directionRead(x, y):
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

#hile True:
#   x = int(input("What is the x coordinate: "))
#   y = int(input("What is the y coordinate: "))

#   print(directionRead(x, y))