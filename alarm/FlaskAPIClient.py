from enum import Enum
import requests
from requests.exceptions import SSLError, RequestException

# Optional: prefer certifi bundle when available
try:
    import certifi
    CERTIFI_BUNDLE = certifi.where()
except Exception:
    CERTIFI_BUNDLE = None

TIMEOUT = 5


class PairingStatus(Enum):
    PAIRED = 0
    PAIRING = 1
    FAILED = 2
    INVALID = 3


class FlaskAPIClient:

    def __init__(self, serial_number, base_url: str = None, verify: object = None):
        # allow overriding base_url for testing
        # self.base_url = base_url or "https://smart-alarm-smartalarmweb.apps.containers.cs.cf.ac.uk"
        # self.base_url = "http://10.2.229.60:5000"
        self.base_url = "http://127.0.0.1:5000"
        self.serial_number = serial_number

        # verify parameter controls SSL verification
        # - None: prefer certifi bundle if available, otherwise use requests default (True)
        # - False: disable verification (INSECURE — only for debugging)
        # - str (path): path to a CA bundle file
        if verify is not None:
            self.verify = verify
        else:
            self.verify = CERTIFI_BUNDLE if CERTIFI_BUNDLE is not None else True

    def _post(self, path: str, payload: dict):
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, json=payload, timeout=TIMEOUT, verify=self.verify)
            return resp
        except SSLError as e:
            print("SSL verification failed when contacting server:", e)
            print(" - If this is a development server using a self-signed or internal CA,")
            print("   consider passing a path to the CA bundle when constructing FlaskAPIClient,")
            print("   or temporarily set verify=False (not for production).")
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
        except Exception:
            return PairingStatus.INVALID

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


    def request_pairing_code(self):
        """
        Requests the pairing code from the server
        :return: pairing code (str)
        """
        path = "/api/device/request-pairing-code"
        payload = {"serial_number": self.serial_number}

        try:
            response = self._post(path, payload)
        except Exception:
            return None

        if response.headers.get("Content-Type", "").lower().startswith("application/json"):
            data = response.json()
        else:
            print("Failed to request pairing code: " + response.text)
            return None

        if response.status_code != 200:
            print("Failed to request pairing code: ", data.get('message', 'unknown reason'))
            return None

        return data.get("pairing_code")

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
        except Exception:
            return None

        if response.headers.get("Content-Type", "").lower().startswith("application/json"):
            data = response.json()
        else:
            print("Failed to get alarms: " + response.text)
            return None

        if response.status_code != 200:
            print("Failed to get alarms: ", data.get('reason', 'unknown reason'))
            return None

        alarms = []
        for alarm in data.get('alarms', []) or []:
            try:
                if alarm.get("enabled") and alarm.get("day_of_week"):
                    alarms.append(alarm)
            except Exception:
                # skip malformed alarm entries
                continue

        print("RETURNING ALARMS")
        return alarms


    def heartbeat(self) -> bool:
        """
        Sends heartbeat update to the server
        :return: True if success, False if failed
        """
        path = "/api/device/heartbeat"
        payload = {"serial_number": self.serial_number}

        try:
            response = self._post(path, payload)
        except Exception:
            return False

        if response.headers.get("Content-Type", "").lower().startswith("application/json"):
            data = response.json()
        else:
            print("Failed to send heartbeat: " + response.text)
            return False

        if response.status_code != 200:
            print("Failed to send heartbeat: ", data.get('reason', 'unknown reason'))
            return False

        return data.get('response') == 'success'
