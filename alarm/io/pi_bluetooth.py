import os
import subprocess
import time
import logging
from typing import Optional, Tuple

import serial
import pexpect

'''
Only a single character gets sent over bluetooth:

> 0 (pi -> arduino) = confirmation request: allows response, switches on button's LED
> 1 (arduino -> pi) = confirmation message: sends response, switches off button's LED
> 2 (pi -> arduino) = end of confirmation window: disallows response, switches off button's LED

See end of file for sample code.
'''

ARDUINO_MAC_ADDRESS = '00:0E:EA:CF:6D:A5'
SERIAL = "/dev/rfcomm0"
HCI_DEVICE = "hci0"
logger = logging.getLogger(__name__)

class Bluetooth:
    def __init__(self):
        self.connection = None
        try:
            self.connection = serial.Serial("/dev/rfcomm0", 9600, timeout=2)
        except serial.SerialException as e:
            logger.warning(f"Could not open /dev/rfcomm0: {e}")
            logger.warning("A connection will be attempted when needed.")

    def process_incoming_message(self, message: str) -> str:
        return str(message).strip('b').strip(r"'").strip()

    def send_message(self, message) -> None:
        if self.connection:
            self.connection.write(message.encode())

    def listen(self, timeout: int) -> Optional[str]:
        if not self.connection:
            return None

        message = []

        for _ in range(timeout // 2):
            incoming = self.process_incoming_message(self.connection.read())
            if incoming == r"\r":
                return self.message_to_string(message)
            message.append(incoming)

        self.send_message("2")
        return None

    def message_to_string(self, message) -> Optional[str]:
        string = ""
        if message is not None:
            for i in message:
                string += i
            return string.strip()
        return None


class BluetoothConfirmation:
    def __init__(self, timeout: int, debug: bool = False) -> None:
        self.awaiting_confirmation = False
        self.received_confirmation = False
        self.received_message = ""

        self.bluetooth_io = Bluetooth()
        self.reply_window = timeout

        self.debug = debug


    def await_confirmation(self) -> None:
        if self.debug:
            logger.debug("Awaiting confirmation...")

        self.received_message = self.bluetooth_io.listen(self.reply_window)

        if self.received_message and "1" in self.received_message:
            self.received_confirmation = True

        else:
            self.received_confirmation = False


    def send_confirmation_request(self) -> None:
        self.received_confirmation = False
        self.bluetooth_io.send_message("0")
        if self.debug:
            logger.debug("Sending confirmation request...")

    def check_confirmation(self) -> bool:
        if self.debug:
            if self.received_confirmation:
                logger.debug("Third-party confirmation received.")
            else:
                logger.debug("Third-party confirmation not received.")

        return self.received_confirmation

class BluetoothSetup:

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self.is_connected = False
        self.rfcomm_process: Optional[subprocess.Popen] = None

    def _log(self, message: str) -> None:
        if self.debug:
            logger.debug("[BT-SETUP] %s", message)

    def _start_rfcomm(self) -> bool:
        """
        Equivalent to:
        sudo rfcomm connect hci0 MAC
        """
        self._log("Starting rfcomm connection...")

        try:
            self.rfcomm_process = subprocess.Popen(
                ["sudo", "-n", "rfcomm", "connect", HCI_DEVICE, ARDUINO_MAC_ADDRESS],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except Exception as e:
            self._log(f"Failed to start rfcomm: {e}")
            return False

        # Give it time to create /dev/rfcomm0
        time.sleep(3)

        if os.path.exists(SERIAL):
            self._log(f"{SERIAL} exists → connection successful")
            return True

        self._log("rfcomm did not create serial device")
        return False

    def _manual_pair_sequence(self) -> bool:
        """
        Fully replicates manual bluetoothctl flow INCLUDING PIN entry.
        """
        self._log("Running manual bluetoothctl sequence with PIN handling...")

        try:
            child = pexpect.spawn("bluetoothctl", encoding="utf-8", timeout=10)

            child.expect([r"\[bluetooth\].*#", r"#"])

            child.sendline(f"remove {ARDUINO_MAC_ADDRESS}")
            child.expect([r"\[bluetooth\].*#", r"#"])

            child.sendline("scan on")
            time.sleep(5)

            child.sendline("scan off")
            child.expect([r"\[bluetooth\].*#", r"#"])

            child.sendline(f"pair {ARDUINO_MAC_ADDRESS}")

            i = child.expect([
                "Enter PIN code",
                "Request PIN code",
                "Pairing successful",
                "Failed to pair",
                "AuthenticationFailed",
                pexpect.TIMEOUT
            ])

            if i in [0, 1]:
                self._log("Sending PIN 1234")
                child.sendline("1234")
                child.expect("Pairing successful")
            elif i == 2:
                self._log("Already paired or pairing succeeded")
            else:
                self._log("Pairing failed or timed out")
                child.close()
                return False

            child.sendline(f"trust {ARDUINO_MAC_ADDRESS}")
            child.expect([r"\[bluetooth\].*#", r"#"])

            child.sendline("quit")
            child.close()

            return True

        except Exception as e:
            self._log(f"Pairing sequence failed: {e}")
            return False

    def connect(self) -> bool:
        """
        Same outward behaviour as before.
        Now mirrors your manual process exactly.
        """
        self._log("=== Bluetooth Setup Start ===")

        # Step 1: try direct rfcomm (what you do first manually)
        if self._start_rfcomm():
            self.is_connected = True
            self._log("Connected immediately via rfcomm")
            return True

        # Step 2: fallback to full pairing flow
        self._log("Initial connect failed → running pairing sequence")

        if not self._manual_pair_sequence():
            self._log("Pairing failed")
            return False

        # Step 3: try rfcomm again
        if self._start_rfcomm():
            self.is_connected = True
            self._log("Connected after pairing")
            return True

        self._log("Bluetooth connection failed completely")
        return False

    def disconnect(self):
        if self.rfcomm_process and self.rfcomm_process.poll() is None:
            self._log("Terminating rfcomm process...")
            self.rfcomm_process.terminate()
            self.rfcomm_process = None

        subprocess.run("sudo -n rfcomm release 0", shell=True)
        self.is_connected = False

    
# sample code
# see top comment for details about messages

if __name__ == "__main__":
    
    bluetooth_setup = BluetoothSetup()
    if bluetooth_setup.connect():

        # initialise bluetooth confirmation class
        # 8 second wait time for a response, and enable console output
        connection = BluetoothConfirmation(8, True)

        # send a confirmation request
        # this will switch on button's LED
        connection.send_confirmation_request()

        # listen for a response from the arduino (for number of seconds specified earlier)
        connection.await_confirmation()

        # check if a response has been received; if not then button's LED switches off
        # returns true if yes, false if no
        connection.check_confirmation()
