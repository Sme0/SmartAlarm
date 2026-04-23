from math import isnan
from typing import List

import grovepi


class TempSensor:
    def __init__(self) -> None:
        self.sensor = 2
        self.temp = 0
        self.humidity = 0

    def check_conditions(self) -> None:
        temp, humidity = grovepi.dht(self.sensor, 0)
        if isnan(temp) or isnan(humidity):
            pass
        else:
            self.temp = temp
            self.humidity = humidity

    def get_temp_and_humidity(self) -> List[int]:
        self.check_conditions()
        return [int(self.temp), int(self.humidity)]
