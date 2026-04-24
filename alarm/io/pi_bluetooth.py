import os
import subprocess
import time
import logging
from typing import Optional, Tuple

import serial

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
        self.debug: bool = debug
        self.is_connected: bool = False
        self.rfcomm_process: Optional[subprocess.Popen] = None

    def _log(self, message: str) -> None:
        if self.debug:
            logger.debug("[BT-SETUP] %s", message)

    def _run_command(self, command: str, sudo: bool = False, timeout: int = 10) -> Tuple[bool, str, str]:
        """
        Execute a shell command and return success status, stdout, stderr.
        """
        try:
            if sudo:
                # Use non-interactive sudo so we fail quickly instead of hanging for a password prompt.
                full_command = f"sudo -n {command}"
            else:
                full_command = command

            self._log(f"Running: {full_command}")
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            success = result.returncode == 0
            return success, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            self._log(f"Command timed out after {timeout}s")
            return False, "", "Command timed out"
        except Exception as e:
            self._log(f"Command failed: {str(e)}")
            return False, "", str(e)

    def _rfcomm_exists(self) -> bool:
        if not os.path.exists(SERIAL):
            self._log(f"{SERIAL} does not exist")
            return False

        try:
            # Non-blocking open: avoid hanging waiting for incoming bytes on an idle serial link.
            test_connection = serial.Serial(SERIAL, 9600, timeout=0.1)
            test_connection.close()
            self._log(f"{SERIAL} is available")
            return True
        except Exception as e:
            self._log(f"{SERIAL} exists but is not usable: {e}")
            return False

    def _is_device_paired(self) -> bool:
        success, stdout, _ = self._run_command(
            f"bluetoothctl info {ARDUINO_MAC_ADDRESS}",
            timeout=5
        )

        if success and "Device" in stdout:
            self._log(f"Device {ARDUINO_MAC_ADDRESS} is already paired")
            return True

        self._log(f"Device {ARDUINO_MAC_ADDRESS} is not paired yet")
        return False
    
    def _scan_for_device(self):
        self._log(f"Scanning for {ARDUINO_MAC_ADDRESS}...")
        
        self._run_command("bluetoothctl scan on", sudo=True, timeout=2)
        time.sleep(5)
        self._run_command("bluetoothctl scan off", sudo=True, timeout=2)

        # Verify device was found
        success, stdout, _ = self._run_command(
            f"bluetoothctl info {ARDUINO_MAC_ADDRESS}",
            timeout=5
        )
        
        if success:
            self._log(f"Found device {ARDUINO_MAC_ADDRESS}")
            return True
        
        self._log(f"Failed to find device {ARDUINO_MAC_ADDRESS}")
        return False

    def _remove_old_connection(self) -> bool:
        self._log(f"Attempting to remove old connection to {ARDUINO_MAC_ADDRESS}...")

        success, _, _ = self._run_command(
            f"bluetoothctl remove {ARDUINO_MAC_ADDRESS}",
            sudo=True,
            timeout=5
        )

        if success:
            self._log("Old connection removed")
            time.sleep(1)
            return True

        # Not finding an old connection is fine
        self._log("No old connection to remove (this is OK)")
        return True

    def _pair_device(self) -> bool:
        self._log(f"Pairing with {ARDUINO_MAC_ADDRESS}...")

        # Attempt pairing
        success, stdout, stderr = self._run_command(
            f"bluetoothctl pair {ARDUINO_MAC_ADDRESS}",
            sudo=True,
            timeout=10
        )

        if not success:
            self._log(f"Pairing failed: {stderr}")
            return False

        if "already paired" in stdout.lower() or "Pairing successful" in stdout:
            self._log("Pairing successful")
            return True

        self._log(f"Pairing response: {stdout}")
        return False
    
    def _trust_device(self) -> bool:
        self._log(f"Trusting {ARDUINO_MAC_ADDRESS}...")

        success, stdout, stderr = self._run_command(
            f"bluetoothctl trust {ARDUINO_MAC_ADDRESS}",
            sudo=True,
            timeout=5
        )

        if success:
            self._log("Device trusted")
            return True

        self._log(f"Trust failed: {stderr}")
        return False

    def _create_rfcomm_connection(self) -> bool:
        self._log(f"Creating rfcomm connection to {ARDUINO_MAC_ADDRESS}...")

        # Release stale mapping for rfcomm0 if present.
        self._run_command("rfcomm release 0", sudo=True, timeout=5)
        time.sleep(1)

        # rfcomm connect is long-running by design; run it in background and poll for /dev/rfcomm0.
        try:
            self.rfcomm_process = subprocess.Popen(
                ["sudo", "-n", "rfcomm", "connect", "0", ARDUINO_MAC_ADDRESS, "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            self._log(f"Failed to start rfcomm process: {e}")
            return False

        for _ in range(20):
            if self._rfcomm_exists():
                self._log("rfcomm connection established")
                self.is_connected = True
                return True
            time.sleep(0.5)

        stderr_output = ""
        if self.rfcomm_process and self.rfcomm_process.poll() is not None:
            _, stderr_output = self.rfcomm_process.communicate()

        self._log(f"rfcomm connection failed: {stderr_output or 'device did not appear'}")
        return False
        
        
    def connect(self) -> bool:
        """
        Establish Bluetooth connection to Arduino.
        Returns True if successful, False otherwise.
        """
        self._log("=== Starting Bluetooth Connection Setup ===")

        # Check if connection already exists and is responsive
        if self._rfcomm_exists():
            self._log(f"{SERIAL} already connected")
            self.is_connected = True
            return True

        # If device is not paired, discover, pair, and trust it
        if not self._is_device_paired():
            # Scan for the Arduino device
            if not self._scan_for_device():
                self._log("Device discovery failed")
                return False
            
            # Clear any old pairing data
            self._remove_old_connection()
            
            # Pair with the Arduino
            if not self._pair_device():
                self._log("Pairing failed")
                return False
        
            # Mark device as trusted for future connections
            self._trust_device()
            
        # Create the virtual serial port (/dev/rfcomm0) and bind it to Arduino
        if not self._create_rfcomm_connection():
            self._log("Failed to create rfcomm connection")
            return False
        
        # Connection successful
        self._log("=== Bluetooth Connection Setup Complete ===")
        return True
    
    def disconnect(self):

        if self.is_connected:
            self._log("Closing Bluetooth connection...")
            self._run_command("rfcomm release 0", sudo=True, timeout=5)
            self.is_connected = False
        if self.rfcomm_process and self.rfcomm_process.poll() is None:
            self.rfcomm_process.terminate()
            self.rfcomm_process = None

    
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
