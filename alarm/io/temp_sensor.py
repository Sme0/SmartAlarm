"""Temperature and humidity sensor access for the Grove DHT module."""

from math import isnan
from typing import List

import grovepi


class TempSensor:
    """Reads temperature and humidity from a Grove DHT sensor on a fixed port."""

    def __init__(self) -> None:
        self.sensor = 2
        self.temp = 0
        self.humidity = 0

    def check_conditions(self) -> None:
        """Read the latest temperature and humidity from the sensor."""
        temp, humidity = grovepi.dht(self.sensor, 0)
        if isnan(temp) or isnan(humidity):
            pass
        else:
            self.temp = temp
            self.humidity = humidity

    def get_temp_and_humidity(self) -> List[int]:
        """Return the latest temperature and humidity as integer values."""
        self.check_conditions()
        return [int(self.temp), int(self.humidity)]
