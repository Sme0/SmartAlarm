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
from alarm.thingsboard_client import ThingsBoardClient

load_dotenv()
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")

if not SERIAL_NUMBER:
    raise ValueError("SERIAL_NUMBER environment variable is not set. Please set it in the .env file.")

flask_api_client = FlaskAPIClient(serial_number=SERIAL_NUMBER)
thingsboard_client = ThingsBoardClient()
thingsboard_client.connect()

device_debug_mode = str(os.getenv("DEVICE_DEBUG_MODE")).lower() in ["true", "y", "yes", "debug"]
if device_debug_mode:
    input_handler = DebugInputHandler(thingsboard_client=thingsboard_client)
    output_handler = DebugOutputHandler()
else:
    input_handler = RaspberryPiInputHandler(thingsboard_client=thingsboard_client)
    output_handler = RaspberryPiOutputHandler()

alarm_controller = AlarmController(input_handler, output_handler)

# Helper functions for debugging and main loop
def _print_debug_help():
    if str(os.getenv("DEVICE_DEBUG_MODE")).lower() != "true":
        return

    print("[DEBUG] SmartAlarm terminal controls")
    print("[DEBUG] When alarm is ringing: type 'dismiss' and press Enter.")
    print("[DEBUG] Maths puzzle / disarm-snooze selection controls: 'left', 'right', 'joy_press'.")
    print("[DEBUG] Memory puzzle controls: 'up', 'down', 'left', 'right'.")
    print("[DEBUG] Commands are read from this terminal while the program is running.\n")


def _flush_inputs_on_state_change(previous_state, current_state):
    """Drop queued inputs whenever the alarm state changes."""
    if previous_state != current_state:
        input_handler.pop_events()


def _handle_alarm_events():
    events = input_handler.pop_events_by_type({
        InputEventType.ALARM_DISMISS,
        InputEventType.ALARM_SNOOZE,
    })

    for event in events:
        if alarm_controller.state != AlarmState.TRIGGERED:
            continue

        if event.event_type == InputEventType.ALARM_DISMISS:
            alarm_controller.run_alarm_interaction()
            break

def pairing_loop():
    if flask_api_client.get_pairing_status() == PairingStatus.PAIRED:
        return

    pairing_code = flask_api_client.request_pairing_code()
    if pairing_code is None:
        output_handler.display_text("None")
    else:
        output_handler.display_text(pairing_code)

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
    last_update_time = time.time()
    previous_state = alarm_controller.state
    previous_alarm_snapshot = None
    while True:

        # Prepare for state change by clearing old inputs
        _flush_inputs_on_state_change(previous_state, alarm_controller.state)
        previous_state = alarm_controller.state

        # Record inputs on this tick
        input_handler.check_inputs(state=alarm_controller.state)
        _handle_alarm_events()

        # Clear old inputs again if state has changed
        _flush_inputs_on_state_change(previous_state, alarm_controller.state)
        previous_state = alarm_controller.state

        alarm_controller.update()
        alarm_controller.check_alarms()

        _flush_inputs_on_state_change(previous_state, alarm_controller.state)
        previous_state = alarm_controller.state

        # Send heartbeat every 15 seconds
        # Comment out if not using webserver yet
        current_time = time.time()
        if current_time - last_update_time >= 15.0:
            success,latest_alarms = flask_api_client.get_alarms()
            if success:
                    alarm_controller.alarms = latest_alarms
            alarm_snapshot = (
                [(alarm.id, alarm.time, alarm.day_of_week, alarm.puzzle_type) for alarm in alarm_controller.alarms],
                [(alarm.id, alarm.time, alarm.day_of_week, alarm.puzzle_type) for alarm in alarm_controller.snooze_alarms],
            )
            if not success:
                print("[DEBUG] Failed to refresh alarms, keeping existing ones")
            if alarm_snapshot != previous_alarm_snapshot:
                print(f"[DEBUG] Active alarms updated: {alarm_controller.alarms}, {alarm_controller.snooze_alarms}")
                previous_alarm_snapshot = alarm_snapshot

            complete_sessions = alarm_controller.peek_complete_sessions()
            if complete_sessions:
                uploaded = flask_api_client.send_complete_sessions(complete_sessions)
                if uploaded:
                    alarm_controller.drop_complete_sessions(complete_sessions.keys())
                else:
                    print("[DEBUG] Failed to upload completed sessions, will retry on next sync")

            last_update_time = current_time

        time.sleep(0.1)

if __name__ == "__main__":
    _print_debug_help()
    pairing_loop()
    main_alarm_loop()
