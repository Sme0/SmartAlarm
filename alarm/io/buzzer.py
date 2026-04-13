import threading
from time import sleep

try:
    import grovepi  # type: ignore
except Exception:  # pragma: no cover - allows debug/non-Pi environments
    grovepi = None


class DebugBuzzer:
    """Fallback buzzer for debug mode or environments without Grove hardware."""

    def __init__(self, volume: int = 3) -> None:
        self.active = False
        self.volume = volume

    def play_single_sound(self, duration: float = 0.5) -> None:
        print(f"[DEBUG BUZZER] single sound for {duration}s at volume {self.volume}")
        sleep(min(duration, 0.05))

    def play_alarm_sound(self) -> None:
        self.active = True
        print(f"[DEBUG BUZZER] alarm started at volume {self.volume}")

    def stop_alarm_sound(self) -> None:
        if self.active:
            print("[DEBUG BUZZER] alarm stopped")
        self.active = False

    def set_alarm_volume(self, volume: int) -> None:
        self.volume = max(0, min(volume, 25))


class Buzzer:
    """Class to control the Grove buzzer used by the physical device."""

    def __init__(self, volume: int = 3) -> None:
        if grovepi is None:
            raise RuntimeError("grovepi is not available. Use DebugBuzzer in debug mode.")

        self.active = False
        self.volume = volume
        self.pin = 5
        self._alarm_thread = None

        grovepi.pinMode(self.pin, "OUTPUT")
        grovepi.analogWrite(self.pin, 0)

    def play_single_sound(self, duration: float = 0.5) -> None:
        """Play a constant sound for a given duration."""
        grovepi.analogWrite(self.pin, 5 * self.volume)
        sleep(duration)
        grovepi.analogWrite(self.pin, 0)

    def alarm_sound(self) -> None:
        """Internal method defining the repeating alarm tune."""
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
        """Starts a background thread to play the alarm sound."""
        if self.active:
            return

        self.active = True
        self._alarm_thread = threading.Thread(target=self.alarm_sound, daemon=True)
        self._alarm_thread.start()

    def stop_alarm_sound(self) -> None:
        """Stops the alarm if it is playing."""
        self.active = False
        if grovepi is not None:
            grovepi.analogWrite(self.pin, 5 * self.volume)
            sleep(0.08)
            grovepi.analogWrite(self.pin, 0)

    def set_alarm_volume(self, volume: int) -> None:
        """Sets the loudness of any noise from the buzzer from 0-25."""
        self.volume = max(0, min(volume, 25))


if __name__ == "__main__":
    alarm = DebugBuzzer() if grovepi is None else Buzzer()

    alarm.play_alarm_sound()
    sleep(2)
    alarm.stop_alarm_sound()
