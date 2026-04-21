from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def group_sleep_records(records: list[dict], night_gap_size=2):
    if not records:
        return []

    sorted_records = sorted(records, key=lambda x: x["start_time"])

    nights = []
    current_night = []

    for record in sorted_records:
        if not current_night:
            # Start the first night
            current_night.append(record)
            continue

        # Check the gap from the last record (in hours)
        gap = (
            (record["start_time"] - current_night[-1]["end_time"]).total_seconds()
        ) / 3600

        if gap > night_gap_size:
            # Gap is too large, therefore a new night
            nights.append(current_night)
            current_night = [record]
        else:
            # Gap is too small, therefore the same night
            current_night.append(record)

    # Overflow data gets added as the final night
    if current_night:
        nights.append(current_night)

    return nights


def parse_apple_dt(value: str):
    """
    Reformats datetime from Apple format to Python format
    :param value: datetime as a string
    :return: the newly formatted datetime
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("invalid datetime value")
    normalized = value.strip()
    # Apple export format uses +0000; Python expects +00:00.
    if (
        len(normalized) >= 5
        and (normalized[-5] in ["+", "-"])
        and normalized[-3] != ":"
    ):
        normalized = normalized[:-2] + ":" + normalized[-2:]
    return datetime.fromisoformat(normalized)


def as_utc(value: datetime) -> datetime | None:
    """Normalise naive/aware datetimes to timezone-aware UTC for safe comparisons."""
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        # Some DB backends/drivers return naive UTC datetimes.
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def next_weekday_utc(day_of_week: int, time_value) -> datetime:
    """Return the next UTC datetime for a target weekday/time."""
    now = utc_now()
    base = now.replace(
        hour=time_value.hour, minute=time_value.minute, second=0, microsecond=0
    )
    days_ahead = (day_of_week - base.weekday()) % 7
    candidate = base + timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def parse_hhmm_time(value: str):
    """Parse HH:MM user input into a time object."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except Exception:
        return None


def minutes_after_midnight(dt: datetime) -> int:
    """
    Convert a datetime to minutes elapsed since midnight.

    :param dt: The datetime to convert.
    :return: Minutes after midnight (0-1439).
    """
    return (dt.hour * 60) + dt.minute


def safe_avg(values: list[float]) -> float:
    """Safely compute the average of a list, returning 0.0 for empty input."""
    return float(sum(values) / len(values)) if values else 0.0


def resolve_timezone(tz_name: str):
    if tz_name:
        try:
            return ZoneInfo(tz_name), tz_name
        except ZoneInfoNotFoundError:
            pass
    return timezone.utc, "UTC"
