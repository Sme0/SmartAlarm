"""Temperature and humidity sensor access for the Grove DHT module."""

from abc import ABC, abstractmethod
from math import isnan
from typing import List


class TempSensor(ABC):
    """Abstract temperature/humidity sensor interface."""

    @abstractmethod
    def get_temp_and_humidity(self) -> List[int]:
        """Return the latest temperature and humidity as integer values."""


class RaspberryPiTempSensor(TempSensor):
    """Reads temperature and humidity from a Grove DHT sensor on a fixed port."""

    def __init__(self) -> None:
        self.sensor = 2
        self.temp = 0
        self.humidity = 0

    def check_conditions(self) -> None:
        """Read the latest temperature and humidity from the sensor."""
        import grovepi

        temp, humidity = grovepi.dht(self.sensor, 0)
        if isnan(temp) or isnan(humidity):
            return
        self.temp = temp
        self.humidity = humidity

    def get_temp_and_humidity(self) -> List[int]:
        """Return the latest temperature and humidity as integer values."""
        self.check_conditions()
        # Reducing temperature reading due to naturally warmer container :)
        return [int(self.temp) - 6, int(self.humidity)]


class DebugTempSensor(TempSensor):
    """Debug sensor that always reports zeroed values."""

    def get_temp_and_humidity(self) -> List[int]:
        """Return placeholder temperature and humidity values."""
        return [0, 0]
