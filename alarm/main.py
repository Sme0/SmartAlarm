"""
This module is the main script for the physical alarm system, controlling the main loop
and delegating tasks to other modules.
"""
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
is_logging_enabled = os.getenv("ENABLE_LOGGING", "").lower() in ["true", "1", "yes"]

if is_logging_enabled:
    logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(module)s: %(message)s")
    logging.getLogger("alarm").setLevel(logging.DEBUG)
    logging.getLogger("__main__").setLevel(logging.DEBUG)
else:
    # Disable logs warning level or below
    logging.disable(logging.WARNING)

from alarm.io.input_handler import DebugInputHandler, RaspberryPiInputHandler
from alarm.io.output_handler import DebugOutputHandler, RaspberryPiOutputHandler
from alarm.io.input_handler import InputEventType
from alarm.io.pi_bluetooth import BluetoothSetup
from alarm.flask_api_client import FlaskAPIClient, PairingStatus
from alarm.device_cache import (
    get_cached_alarms,
    get_cached_server_paired,
    save_cached_alarms,
    save_cached_server_paired,
)
from alarm.alarm_controller import AlarmController
from alarm.alarm_sync import parse_cached_alarms, resolve_alarm_refresh
from alarm.alarm_state import AlarmState
from alarm.thingsboard_client import ThingsBoardClient

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

alarm_controller = AlarmController(input_handler, output_handler, debug_mode=device_debug_mode)

# Helper functions for debugging and main loop
def _print_debug_help():
    if str(os.getenv("DEVICE_DEBUG_MODE")).lower() != "true":
        return

    logger.debug("SmartAlarm terminal controls")
    logger.debug("When alarm is ringing: type 'dismiss' and press Enter.")
    logger.debug("Maths puzzle / disarm-snooze selection controls: 'left', 'right', 'joy_press'.")
    logger.debug("Memory puzzle controls: 'up', 'down', 'left', 'right'.")
    logger.debug("Commands are read from this terminal while the program is running.")


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
    # Last known pairing state lets the device boot in offline mode without blocking.
    cached_paired = get_cached_server_paired()
    pairing_status = flask_api_client.get_pairing_status()

    if pairing_status == PairingStatus.PAIRED:
        # Persist successful server pairing so future offline boots can continue.
        save_cached_server_paired(True)
        return

    if pairing_status == PairingStatus.INVALID:
        if cached_paired:
            logger.info("[SETUP] Pairing status unavailable, using cached paired state.")
            return
        logger.warning("[SETUP] Could not verify pairing and no cached paired state was found.")
        logger.warning("[SETUP] Device will continue in offline/unpaired mode.")
        return

    pairing_code = flask_api_client.request_pairing_code()
    if pairing_code is None:
        output_handler.display_text("None")
    else:
        output_handler.display_text(pairing_code)

    while True:
        status = flask_api_client.get_pairing_status()

        if status == PairingStatus.PAIRED:
            save_cached_server_paired(True)
            logger.info("Successfully paired")
            break

        if status == PairingStatus.INVALID:
            if cached_paired:
                logger.info("[SETUP] Network lost, using cached paired state.")
                break
            output_handler.display_text("Unable to retrieve pairing status/code.")
            logger.warning("[SETUP] Pairing status unavailable. Continuing without pairing.")
            break

        if status == PairingStatus.FAILED:
            pairing_code = flask_api_client.request_pairing_code()
            output_handler.display_text(pairing_code)

        if status == PairingStatus.PAIRING:
            logger.info("Displaying up to date code. No issues")
        time.sleep(5)


# Main alarm loop


def main_alarm_loop():
    last_update_time = time.time()
    previous_state = alarm_controller.state
    previous_alarm_snapshot = None

    # Preload cached alarms so alarms can still run before the first successful sync.
    cached_alarm_rows = get_cached_alarms()
    if cached_alarm_rows:
        restored_alarms = parse_cached_alarms(flask_api_client, cached_alarm_rows)
        if restored_alarms:
            alarm_controller.alarms = restored_alarms
            logger.info("[SETUP] Loaded %s alarms from local cache.", len(restored_alarms))

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
            resolved_alarms, cache_rows = resolve_alarm_refresh(
                flask_api_client,
                alarm_controller.alarms,
                success,
                latest_alarms,
                get_cached_alarms(),
            )
            alarm_controller.alarms = resolved_alarms
            if cache_rows is not None:
                # Refresh local cache with the latest server-confirmed alarm list.
                save_cached_alarms(cache_rows)
            alarm_snapshot = (
                [(alarm.id, alarm.time, alarm.day_of_week, alarm.puzzle_type) for alarm in alarm_controller.alarms],
                [(alarm.id, alarm.time, alarm.day_of_week, alarm.puzzle_type) for alarm in alarm_controller.snooze_alarms],
            )
            if alarm_snapshot != previous_alarm_snapshot:
                logger.debug("Active alarms updated: %s, %s", alarm_controller.alarms, alarm_controller.snooze_alarms)
                previous_alarm_snapshot = alarm_snapshot

            complete_sessions = alarm_controller.peek_complete_sessions()
            if complete_sessions:
                uploaded = flask_api_client.send_complete_sessions(complete_sessions)
                if uploaded:
                    alarm_controller.drop_complete_sessions(complete_sessions.keys())
                else:
                    logger.debug("Failed to upload completed sessions, will retry on next sync")

            last_update_time = current_time

        time.sleep(0.1)

if __name__ == "__main__":
    _print_debug_help()

    # Setup Bluetooth connection to Arduino (skip in debug mode)
    if not device_debug_mode:
        logger.info("[SETUP] Initializing Bluetooth connection to Arduino...")
        bluetooth_setup = BluetoothSetup(debug=True)
        if not bluetooth_setup.connect():
            logger.warning("[SETUP] Bluetooth connection failed. Continuing without Arduino pairing.")
    else:
        logger.info("[SETUP] Skipping Bluetooth setup in debug mode")

    pairing_loop()
    main_alarm_loop()
