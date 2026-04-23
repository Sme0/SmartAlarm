"""Small JSON cache used by the device for offline startup/sync fallback."""

import json
import os
import tempfile
from typing import Any, Dict, Optional


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
        print(f"[CACHE] Failed to load cache file {path}: {exc}")
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
        print(f"[CACHE] Failed to save cache file {path}: {exc}")
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


