from enum import Enum
import os
import logging
import requests
from dotenv import load_dotenv
from requests.exceptions import SSLError, RequestException

from alarm.alarm_controller import Alarm

load_dotenv()

TIMEOUT = 5
logger = logging.getLogger(__name__)

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

    @staticmethod
    def alarm_to_dict(alarm: Alarm) -> dict:
        # Keep Alarm dataclass fields JSON-safe for persistence in the local cache.
        return {
            "id": alarm.id,
            "time": alarm.time,
            "enabled": alarm.enabled,
            "day_of_week": alarm.day_of_week,
            "puzzle_type": alarm.puzzle_type,
            "max_snoozes": alarm.max_snoozes,
            "snooze_count": alarm.snooze_count,
            "source_alarm_id": alarm.source_alarm_id,
        }

    @staticmethod
    def alarm_from_dict(raw_alarm: dict):
        # Shared parser for both server payloads and locally cached alarm rows.
        if not isinstance(raw_alarm, dict):
            return None

        try:
            if not raw_alarm.get("enabled"):
                # Disabled alarms are intentionally ignored by the device runtime.
                return None

            day_of_week = raw_alarm.get("day_of_week")
            if day_of_week is None:
                return None

            alarm_id = raw_alarm.get("id")
            return Alarm(
                id=alarm_id,
                time=raw_alarm.get("time"),
                enabled=raw_alarm.get("enabled"),
                day_of_week=day_of_week,
                puzzle_type=raw_alarm.get("puzzle_type"),
                max_snoozes=raw_alarm.get("max_snoozes"),
                snooze_count=raw_alarm.get("snooze_count", 0),
                source_alarm_id=raw_alarm.get("source_alarm_id", alarm_id),
            )
        except Exception as e:
            logger.debug(f"Skipping malformed alarm entry: {e}")
            return None

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
            logger.debug("SSL verification failed when contacting server.")
            raise
        except RequestException as e:
            logger.debug("HTTP request failed")
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
                logger.debug("Failed to receive pairing status: " + response.text)
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
                logger.debug("Failed to request pairing code: " + response.text)
                return None

            if response.status_code != 200:
                logger.debug("Failed to request pairing code: ", data.get('message', 'unknown reason'))
                return None

            return data.get("pairing_code")

        except Exception:
            return None

    def get_alarms(self):
        """
        Returns updated alarms from the server.
        :return: tuple of success flag and parsed alarms
        """
        path = "/api/device/get-alarms"
        payload = {"serial_number": self.serial_number}

        try:
            response = self._post(path, payload)

            if not response.headers.get("Content-Type", "").lower().startswith("application/json"):
                logger.debug("Failed to get alarms: " + response.text)
                return False, []

            data = response.json()

            if response.status_code != 200:
                logger.debug("Failed to get alarms:", data.get("reason", "unknown reason"))
                return False, []

            alarms = []
            for alarm in data.get("alarms", []):
                parsed_alarm = self.alarm_from_dict(alarm)
                if parsed_alarm is not None:
                    alarms.append(parsed_alarm)

            return True, alarms

        except Exception as e:
            logger.debug(f"Failed to get alarms: {e}")
            return False, []

    def send_complete_sessions(self, complete_sessions: dict) -> bool:
        """
        Sends complete alarm/puzzle session data to the server.

        Expected input format:
        {
            "<alarm_session_id>": {
                "triggered_at": "2026-03-29T12:00:00",
                "puzzle_sessions": [
                    {
                        "alarm_session_id": "<alarm_session_id>",
                        "puzzle_type": "memory",
                        "question": "...",
                        "is_correct": True,
                        "time_taken_seconds": 12.4
                    }
                ],
                "waking_difficulty": 5
            }
        }
        :param complete_sessions: alarm/puzzle session data in the above format
        :return: success
        """
        if not complete_sessions:
            return True

        path = "/api/device/submit-complete-sessions"
        payload = {
            "serial_number": self.serial_number,
            "complete_sessions": complete_sessions,
        }

        try:
            response = self._post(path, payload)

            if response.headers.get("Content-Type", "").lower().startswith("application/json"):
                data = response.json()
            else:
                logger.debug("Failed to submit complete sessions: " + response.text)
                return False

            if response.status_code != 200:
                logger.debug("Failed to submit complete sessions: ", data.get("message", data.get("reason", "unknown reason")))
                return False

            return True

        except Exception:
            return False
