"""
This module is the main script for the physical alarm system, controlling the main loop
and delegating tasks to other modules.
"""
import time

from InputHandler import InputHandler, InputOption
from alarmController import AlarmController
from alarmState import AlarmState

input_handler = InputHandler()

alarm_controller = AlarmController(input_handler)
alarm_controller.alarms.append("10:22:00")
alarm_controller.alarms.append("10:23:00")

# Main alarm loop
while True:

    input_handler.check_inputs()
    if alarm_controller.state == AlarmState.TRIGGERED and input_handler.current_action == InputOption.DISARM:
        alarm_controller.disarm_alarm()

    alarm_controller.update()
    alarm_controller.check_alarms()
    time.sleep(0.1)
