"""
This module is the main script for the physical alarm system, controlling the main loop
and delegating tasks to other modules.
"""
import os
import time

from dotenv import load_dotenv

from alarm.io.input_handler import DebugInputHandler, RaspberryPiInputHandler
from alarm.io.output_handler import DebugOutputHandler, RaspberryPiOutputHandler
from alarm.io.input_handler import InputEventType
from alarm.flask_api_client import FlaskAPIClient, PairingStatus
from alarm.alarm_controller import AlarmController
from alarm.alarm_state import AlarmState

load_dotenv()
SERIAL_NUMBER = "rctvytbi7876urvytfyjg"

flask_api_client = FlaskAPIClient(serial_number=SERIAL_NUMBER)

if str(os.getenv("DEVICE_DEBUG_MODE")).lower() == "true":
    input_handler = DebugInputHandler()
    output_handler = DebugOutputHandler()
elif str(os.getenv("DEVICE_DEBUG_MODE")).lower() == "false":
    input_handler = RaspberryPiInputHandler()
    output_handler = RaspberryPiOutputHandler()
else:
    raise Exception(f"DEVICE_DEBUG_MODE either not defined or valid: {os.getenv('DEVICE_DEBUG_MODE')}")

alarm_controller = AlarmController(input_handler, output_handler)


def _flush_inputs_on_state_change(previous_state, current_state):
    """Drop queued inputs whenever the alarm state changes."""
    if previous_state != current_state:
        input_handler.pop_events()


def _handle_alarm_events():
    events = input_handler.pop_events_by_type({
        InputEventType.ALARM_DISARM,
        InputEventType.ALARM_SNOOZE,
    })

    for event in events:
        if alarm_controller.state != AlarmState.TRIGGERED:
            continue

        if event.event_type == InputEventType.ALARM_DISARM:
            alarm_controller.disarm_alarm()
            break

        if event.event_type == InputEventType.ALARM_SNOOZE:
            alarm_controller.snooze_alarm()
            break

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
    previous_state = alarm_controller.state
    while True:

        _flush_inputs_on_state_change(previous_state, alarm_controller.state)
        previous_state = alarm_controller.state

        input_handler.check_inputs(state=alarm_controller.state)
        _handle_alarm_events()

        _flush_inputs_on_state_change(previous_state, alarm_controller.state)
        previous_state = alarm_controller.state

        alarm_controller.update()
        alarm_controller.check_alarms()

        _flush_inputs_on_state_change(previous_state, alarm_controller.state)
        previous_state = alarm_controller.state

        # Send heartbeat every 30 seconds
        # Comment out if not using webserver yet
        current_time = time.time()
        if current_time - last_heartbeat_time >= 15.0:
            flask_api_client.heartbeat()
            alarm_controller.alarms = flask_api_client.get_alarms()
            print(f"Active alarms: {alarm_controller.alarms}, {alarm_controller.snooze_alarms}")

            last_heartbeat_time = current_time

        time.sleep(0.1)

if __name__ == "__main__":
    pairing_loop()
    main_alarm_loop()
