"""
This module is the main script for the physical alarm system, controlling the main loop
and delegating tasks to other modules.
"""
import time

from InputHandler import InputHandler, InputOption
from alarm.FlaskAPIClient import FlaskAPIClient, PairingStatus
from alarmController import AlarmController
from alarmState import AlarmState

SERIAL_NUMBER = "12345"

flask_api_client = FlaskAPIClient(serial_number=SERIAL_NUMBER)
input_handler = InputHandler()
alarm_controller = AlarmController(input_handler)

# Initial pairing loop
# Comment out if still testing base alarm features without web

if not flask_api_client.get_pairing_status() == PairingStatus.PAIRED:
    #TODO: replace with device screen output
    print(f"Pairing code: {flask_api_client.request_pairing_code()}")
    while True:
        status = flask_api_client.get_pairing_status()

        if status == PairingStatus.PAIRED:
            print("Successfully paired")
            break

        if status == PairingStatus.INVALID:
            print("Invalid code")
            continue

        if status == PairingStatus.FAILED:
            pairing_code = flask_api_client.request_pairing_code()
            #TODO: replace with device screen output
            print(f"Pairing code: {pairing_code}")

        if status == PairingStatus.PAIRING:
            print("Displaying up to date code. No issues")
        time.sleep(5)


# Main alarm loop
last_heartbeat_time = time.time()
while True:

    input_handler.check_inputs()
    if alarm_controller.state == AlarmState.TRIGGERED and input_handler.current_action == InputOption.DISARM:
        alarm_controller.disarm_alarm()

    if alarm_controller.state == AlarmState.TRIGGERED and input_handler.current_action == InputOption.SNOOZE:
        alarm_controller.snooze_alarm()

    alarm_controller.update()
    alarm_controller.check_alarms()

    # Send heartbeat every 30 seconds
    # Comment out if not using webserver yet
    current_time = time.time()
    if current_time - last_heartbeat_time >= 30:
        flask_api_client.heartbeat()
        last_heartbeat_time = current_time

    time.sleep(0.1)
