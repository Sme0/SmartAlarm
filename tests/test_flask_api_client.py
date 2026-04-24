"""Client tests: response parsing, request failures, and alarm payload handling."""

import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from tests.bootstrap import stub_optional_device_dependencies


stub_optional_device_dependencies()

if "requests" not in sys.modules:
    requests = types.ModuleType("requests")
    requests.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests

exceptions = types.ModuleType("requests.exceptions")
exceptions.SSLError = Exception
exceptions.RequestException = Exception
sys.modules.setdefault("requests.exceptions", exceptions)

from alarm.flask_api_client import FlaskAPIClient, PairingStatus


class _Resp:
    def __init__(self, status_code=200, payload=None, content_type="application/json", text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = {"Content-Type": content_type}
        self.text = text

    def json(self):
        return self._payload


class FlaskApiClientTests(unittest.TestCase):
    def test_post_uses_default_tls_verification(self):
        """Client requests should rely on normal TLS verification by default."""
        with patch.dict(os.environ, {"BASE_URL": "https://smartalarm.example"}, clear=False):
            client = FlaskAPIClient("SERIAL-TLS-1")
            response = object()

            with patch("alarm.flask_api_client.requests.post", return_value=response) as post:
                result = client._post("/api/device/pairing-status", {"serial_number": "SERIAL-TLS-1"})

        self.assertIs(result, response)
        self.assertEqual(post.call_args.args[0], "https://smartalarm.example/api/device/pairing-status")
        self.assertNotIn("verify", post.call_args.kwargs)
        self.assertEqual(post.call_args.kwargs["timeout"], 5)

    def test_post_uses_configured_ca_bundle(self):
        """Client requests should use the configured CA bundle when present."""
        with patch.dict(
            os.environ,
            {
                "BASE_URL": "https://smartalarm.example",
                "REQUESTS_CA_BUNDLE": "/tmp/ca.pem",
            },
            clear=False,
        ):
            client = FlaskAPIClient("SERIAL-TLS-2")
            response = object()

            with patch("alarm.flask_api_client.requests.post", return_value=response) as post:
                result = client._post("/api/device/get-alarms", {"serial_number": "SERIAL-TLS-2"})

        self.assertIs(result, response)
        self.assertEqual(post.call_args.args[0], "https://smartalarm.example/api/device/get-alarms")
        self.assertEqual(post.call_args.kwargs["verify"], "/tmp/ca.pem")

    def test_ssl_error_returns_invalid_pairing_status(self):
        """SSL failures should be handled safely by returning an invalid pairing status."""
        client = FlaskAPIClient("SERIAL-TLS-3")
        client._post = Mock(side_effect=exceptions.SSLError("ssl failed"))

        self.assertEqual(client.get_pairing_status(), PairingStatus.INVALID)

    def test_get_pairing_status_maps_json_response(self):
        """JSON pairing responses should map to the matching enum value."""
        client = FlaskAPIClient("SERIAL-1")
        client._post = Mock(return_value=_Resp(payload={"response": "paired"}))

        self.assertEqual(client.get_pairing_status(), PairingStatus.PAIRED)

    def test_get_pairing_status_returns_invalid_for_non_json(self):
        """Non-JSON pairing responses should be treated as invalid."""
        client = FlaskAPIClient("SERIAL-1")
        client._post = Mock(return_value=_Resp(content_type="text/html", text="oops"))

        self.assertEqual(client.get_pairing_status(), PairingStatus.INVALID)

    def test_request_pairing_code_returns_code_or_none(self):
        """Pairing code requests should return the code or None on failure."""
        client = FlaskAPIClient("SERIAL-2")
        client._post = Mock(side_effect=[
            _Resp(payload={"pairing_code": "ABC123"}),
            _Resp(status_code=400, payload={"message": "bad"}),
        ])

        self.assertEqual(client.request_pairing_code(), "ABC123")
        self.assertIsNone(client.request_pairing_code())

    def test_get_alarms_parses_enabled_rows_and_skips_bad_entries(self):
        """Alarm fetches should keep enabled rows and skip unusable ones."""
        client = FlaskAPIClient("SERIAL-3")
        client._post = Mock(return_value=_Resp(payload={
            "alarms": [
                {
                    "id": "a1",
                    "time": "07:30",
                    "enabled": True,
                    "day_of_week": 1,
                    "puzzle_type": "maths",
                    "max_snoozes": 3,
                },
                {
                    "id": "a2",
                    "time": "08:00",
                    "enabled": False,
                    "day_of_week": 2,
                    "puzzle_type": "memory",
                    "max_snoozes": 2,
                },
                {
                    "id": "a3",
                    "enabled": True,
                    "day_of_week": None,
                },
            ]
        }))

        success, alarms = client.get_alarms()

        self.assertTrue(success)
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].id, "a1")
        self.assertEqual(alarms[0].puzzle_type, "maths")

    def test_send_complete_sessions_short_circuits_empty_and_handles_errors(self):
        """Session uploads should skip empty payloads and report failures."""
        client = FlaskAPIClient("SERIAL-4")

        with patch.object(client, "_post") as post:
            self.assertTrue(client.send_complete_sessions({}))
            post.assert_not_called()

        client._post = Mock(return_value=_Resp(status_code=500, payload={"message": "nope"}))
        self.assertFalse(client.send_complete_sessions({"session": {"puzzle_sessions": []}}))

    def test_alarm_dict_round_trip_for_cache(self):
        """Alarm cache helpers should preserve values through dict conversion."""
        client = FlaskAPIClient("SERIAL-5")
        # Mirrors the shape persisted in local JSON cache.
        raw_alarm = {
            "id": "a-cache-1",
            "time": "06:45",
            "enabled": True,
            "day_of_week": 4,
            "puzzle_type": "memory",
            "max_snoozes": 1,
            "snooze_count": 0,
            "source_alarm_id": "a-cache-1",
        }

        parsed = client.alarm_from_dict(raw_alarm)
        self.assertIsNotNone(parsed)
        # Round-trip back to dict to verify serializer compatibility.
        serialized = client.alarm_to_dict(parsed)

        self.assertEqual(serialized["id"], "a-cache-1")
        self.assertEqual(serialized["day_of_week"], 4)
        self.assertEqual(serialized["puzzle_type"], "memory")

    def test_alarm_from_dict_rejects_disabled_rows(self):
        """Disabled alarms should not be restored from cache."""
        client = FlaskAPIClient("SERIAL-6")
        parsed = client.alarm_from_dict({
            "id": "a-disabled",
            "time": "06:45",
            "enabled": False,
            "day_of_week": 4,
            "puzzle_type": "maths",
            "max_snoozes": 1,
        })

        self.assertIsNone(parsed)


if __name__ == "__main__":
    unittest.main()
