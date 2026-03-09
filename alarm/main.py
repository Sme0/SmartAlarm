"""
This module is the main script for the physical alarm system, controlling the main loop
and delegating tasks to other modules.
"""
import time

from alarm.alarmController import AlarmController

alarm_controller = AlarmController()
alarm_controller.alarms.append("09:43:00")

# Main alarm loop
while True:
    alarm_controller.update()
    time.sleep(1)
