from datetime import datetime, timedelta, timezone

from InputHandler import InputHandler, InputOption
from alarm.alarmClockDisplay import Display
from alarmState import AlarmState


def get_current_day_of_week_number():
    """
    Returns the current day of the week as a number (Monday=0, Sunday=6)
    """
    from datetime import datetime
    return datetime.today().weekday()


class AlarmController:

    def __init__(self, input_handler: InputHandler):

        # Initialise input handler from parameters
        self.input_handler = input_handler
        self.display = Display()

        # Current time in 24-hour format
        self.current_time = 0
        self.last_displayed_minute = None

        # Alarms in 24-hour format
        self.alarms = []
        self.snooze_alarms = []

        # Current alarm state
        self.state : AlarmState = AlarmState.WAITING
        self.current_triggered_alarm = None

    def update(self):
        # Update current time
        self.current_time = datetime.utcnow().strftime("%H:%M:%S")


    def check_alarms(self):
        current_minute = datetime.utcnow().minute
        day_of_week = get_current_day_of_week_number()

        # Check each alarm and trigger if needed
        for alarm in (self.alarms + self.snooze_alarms):
            if self.state == AlarmState.WAITING and day_of_week == alarm["day_of_week"] and self.current_time == alarm["time"]:
                self.trigger_alarm(alarm)
                break

        # If there are no alarms triggered
        if self.state == AlarmState.WAITING and current_minute != self.last_displayed_minute:
            self.last_displayed_minute = current_minute
            print(f"Current Time: {datetime.utcnow().strftime('%H:%M')}")
            self.display.set_text(datetime.utcnow().strftime('%H:%M'))




    def trigger_alarm(self, current_alarm):
        self.state = AlarmState.TRIGGERED
        self.current_triggered_alarm = current_alarm

        # TODO: Replace with RPI UI
        print(f"Alarm Triggered: {datetime.utcnow().strftime('%H:%M')}")


    def disarm_alarm(self):
        # TODO: Play game
        self.stop_alarm()

    def snooze_alarm(self):
        # TODO: Play game
        snooze_time = (datetime.utcnow() + timedelta(minutes=5)).strftime("%H:%M") + ":00"
        self.snooze_alarms.append({
            "id": self.current_triggered_alarm["id"] + "-Snooze",
            "time": snooze_time,
            "enabled": True,
            "day_of_week": get_current_day_of_week_number(),
            "puzzle_type": self.current_triggered_alarm["puzzle_type"]
        })
        self.stop_alarm()



    def stop_alarm(self):
        if self.state == AlarmState.TRIGGERED:
            print("Alarm Stopped")
            print(f"Active alarms: {self.alarms}, {self.snooze_alarms}")

            if self.current_triggered_alarm in self.snooze_alarms:
                self.snooze_alarms.remove(self.current_triggered_alarm)
            self.update()
            self.state = AlarmState.WAITING

