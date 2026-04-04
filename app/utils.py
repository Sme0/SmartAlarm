from datetime import datetime


def group_sleep_records(records: list[dict], night_gap_size=2):
    if not records:
        return []

    sorted_records = sorted(records, key=lambda x: x['start_time'])

    nights = []
    current_night = []

    for record in sorted_records:

        if not current_night:
            # Start the first night
            current_night.append(record)
            continue

        # Check the gap from the last record (in hours)
        gap = ((record['start_time'] - current_night[-1]['end_time']).total_seconds()) / 3600

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

def parse_apple_dt(value: str | None):
    """
    Reformats datetime from Apple format to Python format
    :param value: datetime as a string
    :return: the newly formatted datetime
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError('invalid datetime value')
    normalized = value.strip()
    # Apple export format uses +0000; Python expects +00:00.
    if len(normalized) >= 5 and (normalized[-5] in ['+', '-']) and normalized[-3] != ':':
        normalized = normalized[:-2] + ':' + normalized[-2:]
    return datetime.fromisoformat(normalized)