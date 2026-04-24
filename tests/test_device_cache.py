"""Tests for local device cache persistence used during offline operation."""

import os
import tempfile
import unittest

from alarm.device_cache import (
    get_cached_alarms,
    get_cached_server_paired,
    save_cached_alarms,
    save_cached_server_paired,
)


class DeviceCacheTests(unittest.TestCase):
    def setUp(self):
        # Use an isolated cache path per test so reads/writes never leak across tests.
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_cache_path = os.environ.get("DEVICE_CACHE_PATH")
        os.environ["DEVICE_CACHE_PATH"] = os.path.join(self._tmpdir.name, "device-cache.json")

    def tearDown(self):
        if self._old_cache_path is None:
            os.environ.pop("DEVICE_CACHE_PATH", None)
        else:
            os.environ["DEVICE_CACHE_PATH"] = self._old_cache_path
        self._tmpdir.cleanup()

    def test_saves_and_loads_alarm_rows(self):
        rows = [
            {
                "id": "alarm-1",
                "time": "07:30",
                "enabled": True,
                "day_of_week": 1,
                "puzzle_type": "maths",
                "max_snoozes": 2,
                "snooze_count": 0,
                "source_alarm_id": "alarm-1",
            }
        ]

        self.assertTrue(save_cached_alarms(rows))
        self.assertEqual(get_cached_alarms(), rows)

    def test_saves_and_loads_server_pairing_state(self):
        self.assertIsNone(get_cached_server_paired())

        self.assertTrue(save_cached_server_paired(True))
        self.assertTrue(get_cached_server_paired())

        self.assertTrue(save_cached_server_paired(False))
        self.assertFalse(get_cached_server_paired())


if __name__ == "__main__":
    unittest.main()


