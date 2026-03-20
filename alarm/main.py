"""
This module is the main script for the physical alarm system, controlling the main loop
and delegating tasks to other modules.
"""
import time

from alarm.io.input_handler import DebugInputHandler
from alarm.io.output_handler import DebugOutputHandler
from alarm.io.input_handler import InputOption
from alarm.flask_api_client import FlaskAPIClient, PairingStatus
from alarm.alarm_controller import AlarmController
from alarm.alarm_state import AlarmState

SERIAL_NUMBER = "6789"

flask_api_client = FlaskAPIClient()
input_handler = DebugInputHandler()
output_handler = DebugOutputHandler()
alarm_controller = AlarmController(input_handler, output_handler)

def pairing_loop():
    if flask_api_client.get_pairing_status() == PairingStatus.PAIRED:
        return

    pairing_code = flask_api_client.request_pairing_code()
    if pairing_code is None:
        output_handler.display_text("None")
    else:
        output_handler.display_text(flask_api_client.request_pairing_code())

    while True:
        status = flask_api_client.get_pairing_status()

        if status == PairingStatus.PAIRED:
            print("Successfully paired")
            break

        if status == PairingStatus.INVALID:
            output_handler.display_text("Unable to retrieve pairing status/code.")
            continue

        if status == PairingStatus.FAILED:
            pairing_code = flask_api_client.request_pairing_code()
            output_handler.display_text(pairing_code)

        if status == PairingStatus.PAIRING:
            print("Displaying up to date code. No issues")
        time.sleep(5)


# Main alarm loop


def main_alarm_loop():
    last_heartbeat_time = time.time()
    while True:

        input_handler.check_inputs(state=alarm_controller.state)
        if alarm_controller.state == AlarmState.TRIGGERED and input_handler.current_action == InputOption.DISARM:
            alarm_controller.disarm_alarm()

        if alarm_controller.state == AlarmState.TRIGGERED and input_handler.current_action == InputOption.SNOOZE:
            alarm_controller.snooze_alarm()

        alarm_controller.update()
        alarm_controller.check_alarms()

        # Send heartbeat every 30 seconds
        # Comment out if not using webserver yet
        current_time = time.time()
        if current_time - last_heartbeat_time >= 15.0:
            flask_api_client.heartbeat()
            alarm_controller.alarms = flask_api_client.get_alarms()
            last_heartbeat_time = current_time

        time.sleep(0.1)

if __name__ == "__main__":
    pairing_loop()
    main_alarm_loop()
