import threading
from time import sleep

import grovepi


class Buzzer:
    """
    Class to control raspberry pi buzzer.
    """

    def __init__(self, volume: int = 3) -> None:
        self.active = False
        self.volume = volume
        self.pin = 5

        grovepi.pinMode(self.pin, "OUTPUT")
        grovepi.analogWrite(self.pin, 0)

    def play_single_sound(self, duration: float = 0.5) -> None:
        """
        Play a constant sound for a given duration.
        """
        grovepi.analogWrite(self.pin, 5 * self.volume)
        sleep(duration)
        grovepi.analogWrite(self.pin, 0)

    def alarm_sound(self) -> None:
        """
        Internal method defining the alarm tune
        """
        while self.active:
            for _ in range(4):
                grovepi.analogWrite(self.pin, 10 * self.volume)
                sleep(0.05)
                grovepi.analogWrite(self.pin, 1 * self.volume)
                sleep(0.1)

                if not self.active:
                    grovepi.analogWrite(self.pin, 0)
                    return

            grovepi.analogWrite(self.pin, 0)
            sleep(0.4)

        grovepi.analogWrite(self.pin, 0)

    def play_alarm_sound(self) -> None:
        """
        Starts a thread to play the alarm sound
        """
        self.active = True
        buzzer_thread = threading.Thread(target=self.alarm_sound)
        buzzer_thread.start()

    def stop_alarm_sound(self) -> None:
        """
        Stops the alarm if it's playing
        """
        self.active = False
        grovepi.analogWrite(self.pin, 5 * self.volume)
        sleep(0.08)
        grovepi.analogWrite(self.pin, 0)

    def set_alarm_volume(self, volume: int) -> None:
        """
        Sets the loudness of any noise from the buzzer from 0-25
        """
        self.volume = max(0, min(volume, 25))


if __name__ == "__main__":
    alarm = Buzzer()

    # play alarm at default volume for four seconds
    alarm.play_alarm_sound()
    sleep(4)
    alarm.stop_alarm_sound()

    # set alarm volume to 1 (minimum)
    alarm.set_alarm_volume(1)

    sleep(0.6)

    # play alarm again for two seconds
    alarm.play_alarm_sound()
    sleep(2)
    alarm.stop_alarm_sound()
