# Shared Redis write-lock helpers for generated OWUI MemPalace plugins.
# This file is injected into generated plugin artifacts by scripts/generate_plugins.py.

import hashlib
import os
import random
import time
import uuid
from contextlib import contextmanager


class _OwuiMpLockUnavailable(Exception):
    """Raised when the MemPalace Redis write lock cannot be acquired."""


_OWUI_MP_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
else
  return 0
end
"""


def _owui_mp_get_env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name, "")
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _owui_mp_get_env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "")
    if value == "":
        return default
    try:
        return int(value)
    except Exception:
        return default


def _owui_mp_get_sentinels_from_env(hosts: str, port: str) -> list[tuple[str, int]]:
    if not hosts:
        return []
    try:
        sentinel_port = int(port)
    except Exception:
        sentinel_port = 26379
    return [(host.strip(), sentinel_port) for host in hosts.split(",") if host.strip()]


def _owui_mp_get_lock_key(palace_path: str, key_prefix: str) -> str:
    digest = hashlib.sha256((palace_path or "").encode("utf-8")).hexdigest()
    prefix = key_prefix or "open-webui"
    return f"{prefix}:mempalace:lock:write:{digest}"


def _owui_mp_get_redis_client():
    redis_url = (os.environ.get("REDIS_URL") or "").strip()
    if not redis_url:
        return None

    redis_cluster = _owui_mp_get_env_bool("REDIS_CLUSTER", False)
    sentinel_hosts = (os.environ.get("REDIS_SENTINEL_HOSTS") or "").strip()
    sentinel_port = (os.environ.get("REDIS_SENTINEL_PORT") or "26379").strip()

    try:
        from open_webui.utils.redis import get_redis_connection  # type: ignore

        return get_redis_connection(
            redis_url=redis_url,
            redis_sentinels=_owui_mp_get_sentinels_from_env(sentinel_hosts, sentinel_port),
            redis_cluster=redis_cluster,
            async_mode=False,
        )
    except Exception:
        pass

    try:
        import redis  # type: ignore
    except Exception:
        return None

    try:
        if redis_cluster:
            return redis.RedisCluster.from_url(redis_url, decode_responses=True)
        return redis.Redis.from_url(redis_url, decode_responses=True)
    except Exception:
        return None


def _owui_mp_acquire_lock(client, key: str, token: str, ttl_seconds: int, wait_seconds: int) -> bool:
    deadline = time.monotonic() + max(0, int(wait_seconds))
    ttl = max(1, int(ttl_seconds))
    while True:
        try:
            if client.set(key, token, nx=True, ex=ttl):
                return True
        except Exception:
            return False
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1 + random.random() * 0.15)


def _owui_mp_release_lock(client, key: str, token: str) -> None:
    try:
        client.eval(_OWUI_MP_RELEASE_SCRIPT, 1, key, token)
    except Exception:
        pass


@contextmanager
def _owui_mp_write_lock(*, enabled: bool, palace_path: str, ttl_seconds: int, wait_seconds: int, key_prefix: str = "open-webui"):
    if not enabled:
        yield
        return

    client = _owui_mp_get_redis_client()
    if client is None:
        raise _OwuiMpLockUnavailable("MemPalace write lock unavailable; retry shortly")

    key = _owui_mp_get_lock_key(palace_path, key_prefix)
    token = str(uuid.uuid4())

    acquired = _owui_mp_acquire_lock(client, key, token, ttl_seconds, wait_seconds)
    if not acquired:
        raise _OwuiMpLockUnavailable("MemPalace write lock unavailable; retry shortly")

    try:
        yield
    finally:
        _owui_mp_release_lock(client, key, token)
