"""Helpers for keeping device alarms available during offline sync failures."""

import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

from alarm.alarm_controller import Alarm

if TYPE_CHECKING:
    from alarm.flask_api_client import FlaskAPIClient

logger = logging.getLogger(__name__)


def parse_cached_alarms(client: "FlaskAPIClient", cached_alarm_rows: list) -> List[Alarm]:
    """Parse cached JSON rows into runtime alarms, skipping unusable entries."""
    restored_alarms = []
    for row in cached_alarm_rows or []:
        parsed_alarm = client.alarm_from_dict(row)
        if parsed_alarm is not None:
            restored_alarms.append(parsed_alarm)
    return restored_alarms


def resolve_alarm_refresh(
    client: "FlaskAPIClient",
    current_alarms: List[Alarm],
    sync_success: bool,
    latest_alarms: List[Alarm],
    cached_alarm_rows: list,
) -> Tuple[List[Alarm], Optional[list]]:
    """
    Choose the runtime alarm list after a sync attempt.

    Returns the alarms the device should keep using, plus cache rows to persist
    when the server sync succeeded.
    """
    if sync_success:
        cache_rows = [client.alarm_to_dict(alarm) for alarm in latest_alarms]
        return list(latest_alarms), cache_rows

    if current_alarms:
        logger.debug("Failed to refresh alarms, keeping existing ones")
        return list(current_alarms), None

    fallback_alarms = parse_cached_alarms(client, cached_alarm_rows)
    if fallback_alarms:
        logger.debug(
            "Loaded %s cached alarms due to sync failure", len(fallback_alarms)
        )
        return fallback_alarms, None

    logger.debug("Failed to refresh alarms and no cached alarms were usable")
    return [], None
