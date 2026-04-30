"""Alarm sync tests: cached alarms should keep the device running offline."""

import sys
import types
import unittest

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

from alarm.alarm_controller import Alarm
from alarm.alarm_sync import parse_cached_alarms, resolve_alarm_refresh, prune_snooze_alarms
from alarm.flask_api_client import FlaskAPIClient


class AlarmSyncTests(unittest.TestCase):
    def test_parse_cached_alarms_restores_usable_rows(self):
        """Cached alarm rows should be restored into runtime alarms."""
        client = FlaskAPIClient("SYNC-1")
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
            },
            {
                "id": "alarm-2",
                "time": "08:00",
                "enabled": False,
                "day_of_week": 2,
                "puzzle_type": "memory",
                "max_snoozes": 1,
            },
        ]

        restored = parse_cached_alarms(client, rows)

        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].id, "alarm-1")

    def test_sync_failure_uses_cached_alarms_when_runtime_empty(self):
        """A failed sync should restore cached alarms if no live alarms are loaded."""
        client = FlaskAPIClient("SYNC-2")
        cached_rows = [
            {
                "id": "alarm-cache",
                "time": "06:45",
                "enabled": True,
                "day_of_week": 4,
                "puzzle_type": "memory",
                "max_snoozes": 1,
                "snooze_count": 0,
                "source_alarm_id": "alarm-cache",
            }
        ]

        alarms, cache_rows = resolve_alarm_refresh(
            client,
            current_alarms=[],
            sync_success=False,
            latest_alarms=[],
            cached_alarm_rows=cached_rows,
        )

        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].id, "alarm-cache")
        self.assertIsNone(cache_rows)

    def test_sync_failure_keeps_existing_runtime_alarms(self):
        """A failed sync should keep current runtime alarms before falling back to cache."""
        client = FlaskAPIClient("SYNC-3")
        current = [
            Alarm(
                id="live-alarm",
                time="07:15",
                enabled=True,
                day_of_week=2,
                puzzle_type="maths",
                max_snoozes=3,
                snooze_count=0,
                source_alarm_id="live-alarm",
            )
        ]
        cached_rows = [
            {
                "id": "cached-alarm",
                "time": "08:45",
                "enabled": True,
                "day_of_week": 3,
                "puzzle_type": "memory",
                "max_snoozes": 1,
                "snooze_count": 0,
                "source_alarm_id": "cached-alarm",
            }
        ]

        alarms, cache_rows = resolve_alarm_refresh(
            client,
            current_alarms=current,
            sync_success=False,
            latest_alarms=[],
            cached_alarm_rows=cached_rows,
        )

        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].id, "live-alarm")
        self.assertIsNone(cache_rows)

    def test_successful_sync_returns_cache_rows_to_persist(self):
        """A successful sync should return rows that can be saved to cache."""
        client = FlaskAPIClient("SYNC-4")
        latest = [
            Alarm(
                id="server-alarm",
                time="09:00",
                enabled=True,
                day_of_week=0,
                puzzle_type="maths",
                max_snoozes=2,
                snooze_count=0,
                source_alarm_id="server-alarm",
            )
        ]

        alarms, cache_rows = resolve_alarm_refresh(
            client,
            current_alarms=[],
            sync_success=True,
            latest_alarms=latest,
            cached_alarm_rows=[],
        )

        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].id, "server-alarm")
        self.assertEqual(cache_rows[0]["id"], "server-alarm")

    def test_prune_snooze_alarms_drops_deleted_sources(self):
        """Snoozed alarms should be removed if their source alarms were deleted."""
        latest = [
            Alarm(
                id="alarm-keep",
                time="07:00",
                enabled=True,
                day_of_week=1,
                puzzle_type="maths",
                max_snoozes=2,
                snooze_count=0,
                source_alarm_id="alarm-keep",
            )
        ]
        snoozes = [
            Alarm(
                id="alarm-keep-Snooze-1",
                time="07:05",
                enabled=True,
                day_of_week=1,
                puzzle_type="maths",
                max_snoozes=2,
                snooze_count=1,
                source_alarm_id="alarm-keep",
            ),
            Alarm(
                id="alarm-drop-Snooze-1",
                time="08:05",
                enabled=True,
                day_of_week=2,
                puzzle_type="memory",
                max_snoozes=2,
                snooze_count=1,
                source_alarm_id="alarm-drop",
            ),
        ]

        pruned = prune_snooze_alarms(snoozes, latest)

        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0].source_alarm_id, "alarm-keep")

    def test_prune_snooze_alarms_clears_when_no_latest(self):
        """When all alarms are deleted, snoozes should be cleared too."""
        snoozes = [
            Alarm(
                id="alarm-keep-Snooze-1",
                time="07:05",
                enabled=True,
                day_of_week=1,
                puzzle_type="maths",
                max_snoozes=2,
                snooze_count=1,
                source_alarm_id="alarm-keep",
            )
        ]

        pruned = prune_snooze_alarms(snoozes, [])

        self.assertEqual(pruned, [])


if __name__ == "__main__":
    unittest.main()
