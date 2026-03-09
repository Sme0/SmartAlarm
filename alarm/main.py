"""
This module is the main script for the physical alarm system, controlling the main loop
and delegating tasks to other modules.
"""
import time

from alarm.InputHandler import InputHandler
from alarm.alarmController import AlarmController

input_handler = InputHandler()

alarm_controller = AlarmController(input_handler)
alarm_controller.alarms.append("10:22:00")
alarm_controller.alarms.append("10:23:00")

# Main alarm loop
while True:

    alarm_controller.update()
    alarm_controller.check_alarms()
    time.sleep(0.1)
