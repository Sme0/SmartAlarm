"""Small JSON cache used by the device for offline startup/sync fallback."""

import json
import os
import tempfile
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CACHE_FILE_ENV = "DEVICE_CACHE_PATH"
DEFAULT_CACHE_FILE = os.path.join(os.path.dirname(__file__), "device_cache.json")


def _cache_path() -> str:
    # Allow overriding the cache location for tests and deployments.
    return os.getenv(CACHE_FILE_ENV, DEFAULT_CACHE_FILE)


def _load_cache() -> Dict[str, Any]:
    path = _cache_path()
    try:
        with open(path, "r", encoding="utf-8") as cache_file:
            data = json.load(cache_file)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        # Missing cache is expected on first boot.
        return {}
    except Exception as exc:
        logger.error(f"Failed to load cache file {path}: {exc}")
        return {}


def _save_cache(data: Dict[str, Any]) -> bool:
    path = _cache_path()
    directory = os.path.dirname(path) or "."

    try:
        os.makedirs(directory, exist_ok=True)
        # Write to a temp file, then atomically replace to avoid partial writes.
        with tempfile.NamedTemporaryFile("w", delete=False, dir=directory, encoding="utf-8") as temp_file:
            json.dump(data, temp_file)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = temp_file.name
        os.replace(temp_path, path)
        return True
    except Exception as exc:
        logger.error(f"Failed to save cache file {path}: {exc}")
        return False


def get_cached_alarms() -> list:
    # Returns raw alarm rows; parsing into Alarm objects happens in main/client code.
    cache = _load_cache()
    alarms = cache.get("alarms", [])
    return alarms if isinstance(alarms, list) else []


def save_cached_alarms(alarms: list) -> bool:
    cache = _load_cache()
    cache["alarms"] = alarms
    return _save_cache(cache)


def get_cached_server_paired() -> Optional[bool]:
    # None means "no known server pairing state cached yet".
    cache = _load_cache()
    paired = cache.get("server_paired")
    return paired if isinstance(paired, bool) else None


def save_cached_server_paired(is_paired: bool) -> bool:
    cache = _load_cache()
    cache["server_paired"] = bool(is_paired)
    return _save_cache(cache)


# --- Permissions cache helpers ---
def get_cached_permissions() -> dict:
    """
    Returns cached user data permissions.
    Structure:
    {
        "collect_alarm_sessions": bool,
        "collect_brainteaser_performance": bool,
        "ask_waking_difficulty": bool,
        "use_health_data": bool
    }
    """
    cache = _load_cache()
    permissions = cache.get("permissions", {})
    return permissions if isinstance(permissions, dict) else {}


def save_cached_permissions(permissions: dict) -> bool:
    """
    Saves user data permissions to cache.
    """
    cache = _load_cache()
    cache["permissions"] = permissions
    return _save_cache(cache)


def get_permission_value(key: str, default: bool = False) -> bool:
    """
    Helper to safely fetch a single permission flag.
    """
    permissions = get_cached_permissions()
    value = permissions.get(key)
    return bool(value) if isinstance(value, bool) else default


# --- Convenience wrappers for permission checks ---
def can_collect_alarm_sessions() -> bool:
    return get_permission_value("collect_alarm_sessions", True)


def can_collect_brainteaser_performance() -> bool:
    return get_permission_value("collect_brainteaser_performance", True)


def can_ask_waking_difficulty() -> bool:
    return get_permission_value("ask_waking_difficulty", True)


def can_use_health_data() -> bool:
    return get_permission_value("use_health_data", False)
