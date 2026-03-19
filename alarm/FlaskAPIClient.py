from enum import Enum

import requests

TIMEOUT = 5

class PairingStatus(Enum):
    PAIRED = 0
    PAIRING = 1
    FAILED = 2
    INVALID = 3

class FlaskAPIClient:

    def __init__(self, serial_number):
        # self.base_url = "https://smart-alarm-smartalarmweb.apps.containers.cs.cf.ac.uk"
        self.base_url = "http://10.2.229.60:5000"
        self.serial_number = serial_number

    def get_pairing_status(self) -> PairingStatus:
        """
        Returns the pairing status of the device
        :return: PairingStatus
        """
        url = f"{self.base_url}/api/device/pairing-status"
        payload = {
            "serial_number": self.serial_number
        }

        try:
            response = requests.post(url, json=payload, timeout=TIMEOUT)

            if response.headers.get("Content-Type") == "application/json":
                data = response.json()
            else:
                print("Failed to receive pairing status: " + response.text)
                return PairingStatus.INVALID

            raw_pairing_status = data.get("response")
            if raw_pairing_status == "paired":
                return PairingStatus.PAIRED
            elif raw_pairing_status == "pairing":
                return PairingStatus.PAIRING
            elif raw_pairing_status == "failed":
                return PairingStatus.FAILED
            else:
                return PairingStatus.INVALID



        except requests.RequestException as e:
            print("Pairing status request failed: ", e)
            return PairingStatus.INVALID

    def request_pairing_code(self):
        """
        Requests the pairing code from the server
        :return: pairing code (str)
        """
        url = f"{self.base_url}/api/device/request-pairing-code"
        payload = {
            "serial_number": self.serial_number
        }

        try:
            response = requests.post(url, json=payload, timeout=TIMEOUT)

            if response.headers.get("Content-Type") == "application/json":
                data = response.json()
            else:
                print("Failed to request pairing code: " + response.text)
                return None

            if response.status_code != 200:
                print("Failed to request pairing code: ", data.get('message', 'unknown reason'))
                return None

            return data.get("pairing_code")

        except requests.RequestException as e:
            print("Pairing code request failed:", e)
            return None

    def get_alarms(self):
        """
        Returns updated alarms from the server
        :return: List of string-formatted alarms
        """
        print("GETTING ALARMS")
        url = f"{self.base_url}/api/device/get-alarms"
        payload = {
            "serial_number": self.serial_number
        }

        try:
            response = requests.post(url, json=payload, timeout=TIMEOUT)

            if response.headers.get("Content-Type") == "application/json":
                data = response.json()
            else:
                print("Failed to get alarms: " + response.text)
                return None

            if response.status_code != 200:
                print("Failed to get alarms: ", data.get('reason', 'unknown reason'))
                return None

            alarms = []

            for alarm in data.get('alarms'):
                if alarm["enabled"] and alarm["day_of_week"]:
                    alarms.append(alarm)

            print("RETURNING ALARMS")
            return alarms

        except requests.RequestException as e:
            print("Alarm request failed:", e)
            return None


    def heartbeat(self) -> bool:
        """
        Sends heartbeat update to the server
        :return: True if success, False if failed
        """
        url = f"{self.base_url}/api/device/heartbeat"
        payload = {
            "serial_number": self.serial_number
        }

        try:
            response = requests.post(url, json=payload, timeout=TIMEOUT)

            if response.headers.get("Content-Type") == "application/json":
                data = response.json()
            else:
                print("Failed to send heartbeat: " + response.text)
                return False

            if response.status_code != 200:
                print("Failed to send heartbeat: ", data.get('reason', 'unknown reason'))
                return False

            if data.get('response') == 'success':
                return True
            else:
                return False

        except requests.RequestException as e:
            print("Heartbeat failed:", e)
            return False
