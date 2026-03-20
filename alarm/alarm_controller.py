from datetime import datetime, timedelta
from alarm.io.output_handler import OutputHandler
from alarm.io.input_handler import InputHandler
from alarm.alarm_state import AlarmState

def get_current_day_of_week_number():
    """
    Returns the current day of the week as a number (Monday=0, Sunday=6)
    """
    return datetime.today().weekday()


class AlarmController:

    def __init__(self, input_handler: InputHandler, output_handler: OutputHandler):

        self.input_handler = input_handler
        self.output_handler = output_handler

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
            if self.state == AlarmState.WAITING and day_of_week == alarm["day_of_week"] and self.current_time == (alarm["time"] + ":00"):
                self.trigger_alarm(alarm)
                break

        # If there are no alarms triggered
        if self.state == AlarmState.WAITING and current_minute != self.last_displayed_minute:
            self.last_displayed_minute = current_minute
            self.output_handler.display_text(datetime.utcnow().strftime('%H:%M'))




    def trigger_alarm(self, current_alarm):
        self.state = AlarmState.TRIGGERED
        self.current_triggered_alarm = current_alarm

        self.output_handler.display_text(f"Alarm Triggered: {datetime.utcnow().strftime('%H:%M')}")

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

