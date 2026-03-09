from datetime import datetime

from alarm.alarmState import AlarmState


class AlarmController:
    def __init__(self):
        # Current time in 24-hour format
        self.current_time = 0

        # Alarms in 24-hour format
        self.alarms = []
        self.state : AlarmState = AlarmState.WAITING

    def update(self):
        self.current_time = datetime.now().strftime("%H:%M:%S")

        for alarm in self.alarms:
            if self.state == AlarmState.WAITING and self.current_time == alarm:
                self.trigger_alarm()
        else:
            print(f"Current Time: {self.current_time}")


    def trigger_alarm(self):
        self.state = AlarmState.TRIGGERED

        # TODO: Replace with RPI UI
        print(f"Alarm Triggered: {self.current_time}")

        # TODO: Replace with RPI button control
        user_input = input("Respond to stop alarm")

        #TODO: Add snooze
        if user_input:
            self.stop_alarm()


    def stop_alarm(self):
        if self.state == AlarmState.TRIGGERED:
            print("Alarm Stopped")
            self.update()
            self.state = AlarmState.WAITING

