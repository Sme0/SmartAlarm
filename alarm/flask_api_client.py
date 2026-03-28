from enum import Enum
import os
import requests
from dotenv import load_dotenv
from requests.exceptions import SSLError, RequestException

from alarm.alarm_controller import Alarm

load_dotenv()

TIMEOUT = 5

class PairingStatus(Enum):
    PAIRED = 0
    PAIRING = 1
    FAILED = 2
    INVALID = 3


class FlaskAPIClient:

    def __init__(self, serial_number):
        # allow overriding base_url for testing
        self.base_url = os.getenv("BASE_URL")
        self.serial_number = serial_number

    def _post(self, path: str, payload: dict):
        url = f"{self.base_url}{path}"
        try:
            verify_path = os.getenv("REQUESTS_CA_BUNDLE")
            if not verify_path or verify_path is None:
                resp = requests.post(url, json=payload, timeout=TIMEOUT)
            else:
                resp = requests.post(url, json=payload, timeout=TIMEOUT, verify=verify_path if verify_path else True)
            return resp
        except SSLError as e:
            print("SSL verification failed when contacting server:", e)
            raise
        except RequestException as e:
            print("HTTP request failed:", e)
            raise

    def get_pairing_status(self) -> PairingStatus:
        """
        Returns the pairing status of the device
        :return: PairingStatus
        """
        path = "/api/device/pairing-status"
        payload = {"serial_number": self.serial_number}

        try:
            response = self._post(path, payload)

            if response.headers.get("Content-Type", "").lower().startswith("application/json"):
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

        except Exception:
            return PairingStatus.INVALID



    def request_pairing_code(self):
        """
        Requests the pairing code from the server
        :return: pairing code (str)
        """
        path = "/api/device/request-pairing-code"
        payload = {"serial_number": self.serial_number}

        try:
            response = self._post(path, payload)

            if response.headers.get("Content-Type", "").lower().startswith("application/json"):
                data = response.json()
            else:
                print("Failed to request pairing code: " + response.text)
                return None

            if response.status_code != 200:
                print("Failed to request pairing code: ", data.get('message', 'unknown reason'))
                return None

            return data.get("pairing_code")

        except Exception:
            return None

    def get_alarms(self):
        """
        Returns updated alarms from the server
        :return: List of string-formatted alarms
        """
        print("GETTING ALARMS")
        path = "/api/device/get-alarms"
        payload = {"serial_number": self.serial_number}

        try:
            response = self._post(path, payload)
            if response.headers.get("Content-Type", "").lower().startswith("application/json"):
                data = response.json()
            else:
                print("Failed to get alarms: " + response.text)
                return None

            if response.status_code != 200:
                print("Failed to get alarms: ", data.get('reason', 'unknown reason'))
                return None

            alarms = []
            for alarm in data.get('alarms'):
                try:
                    if alarm.get("enabled") and alarm.get("day_of_week") is not None:
                        alarms.append(Alarm(
                            id=alarm.get("id"),
                            time=alarm.get("time"),
                            enabled=alarm.get("enabled"),
                            day_of_week=alarm.get("day_of_week"),
                            puzzle_type=alarm.get("puzzle_type"),
                            max_snoozes=alarm.get("max_snoozes"),
                            snooze_count=0,
                            source_alarm_id=alarm.get("id")
                        ))
                except Exception:
                    # skip malformed alarm entries
                    continue
            print("RETURNING ALARMS")
            return alarms

        except Exception:
            return None