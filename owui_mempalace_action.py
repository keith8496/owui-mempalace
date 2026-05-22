# ---------------------------------------------------------------------------
# GENERATED FILE - DO NOT EDIT DIRECTLY
# Source template: plugin_src/owui_mempalace_action.src.py
# Shared injected block: plugin_src/_shared_lock.py
# Regenerate with: python scripts/generate_plugins.py
# ---------------------------------------------------------------------------

"""
title: Save Chat to MemPalace
author: Keith
version: 0.1.0
description: Open WebUI action for saving user/assistant exchanges to MemPalace.
requirements: mempalace>=3.3.5

Open WebUI Action: Save current chat to MemPalace.

Upload this file as an Open WebUI Action function.

This action is intentionally conservative. It harvests the message list passed
by Open WebUI to the action, pairs user/assistant exchanges, and stores each
exchange as a MemPalace drawer with deterministic Open WebUI provenance.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

# --- BEGIN injected from plugin_src/_shared_lock.py ---
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
# --- END injected from plugin_src/_shared_lock.py ---

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore

    def Field(default=None, **_: Any):  # type: ignore
        return default


class Action:
    class Valves(BaseModel):
        default_wing: str = Field(default="open_webui", description="Wing used for harvested chats.")
        default_room: str = Field(default="conversations", description="Room used for exchange drawers.")
        dry_run: bool = Field(default=False, description="Preview counts without writing to MemPalace.")
        max_exchanges: int = Field(default=100, ge=1, le=1000, description="Maximum exchanges per action run.")
        max_exchange_chars: int = Field(default=20000, ge=1000, le=100000)
        palace_path: str = Field(
            default="/app/backend/data/mempalace",
            description="MemPalace palace directory for Open WebUI persistent storage.",
        )
        use_redis_write_lock: bool = Field(default=False, description="Serialize harvested chat writes with Redis.")
        redis_harvest_lock_ttl_seconds: int = Field(default=300, ge=1, le=3600)
        redis_lock_wait_seconds: int = Field(default=10, ge=0, le=120)

    def __init__(self) -> None:
        self.valves = self.Valves()

    def _ensure_palace_path(self) -> None:
        """Set the MemPalace palace path before the lazy runtime import."""
        palace_path = str(getattr(self.valves, "palace_path", "") or "").strip()
        if palace_path and not os.environ.get("MEMPALACE_PALACE_PATH", "").strip():
            os.environ["MEMPALACE_PALACE_PATH"] = palace_path

    def _mcp_server(self):
        self._ensure_palace_path()
        from mempalace import mcp_server

        return mcp_server

    def _write_lock_kwargs(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.valves.use_redis_write_lock),
            "palace_path": str(self.valves.palace_path),
            "ttl_seconds": int(self.valves.redis_harvest_lock_ttl_seconds),
            "wait_seconds": int(self.valves.redis_lock_wait_seconds),
            "key_prefix": (os.environ.get("REDIS_KEY_PREFIX") or "open-webui").strip() or "open-webui",
        }

    async def action(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Any = None,
        **_: Any,
    ) -> dict:
        """Save the current Open WebUI chat branch to MemPalace."""
        messages = body.get("messages") or []
        if not isinstance(messages, list):
            return {"success": False, "error": "No message list provided to action"}

        chat_id_raw = body.get("chat_id") or body.get("id") or (__metadata__ or {}).get("chat_id") or "unknown"
        chat_id = str(chat_id_raw)
        chat_uri_id = self._uri_part(chat_id_raw)
        exchanges = self._pair_exchanges(messages)[: int(self.valves.max_exchanges)]
        if not exchanges:
            return {"success": False, "error": "No user/assistant exchanges found"}

        if __event_emitter__:
            await self._emit_best_effort(__event_emitter__, f"MemPalace: preparing {len(exchanges)} exchanges", done=False)

        imported = 0
        skipped = 0
        errors: list[str] = []

        if self.valves.dry_run:
            if __event_emitter__:
                await self._emit_best_effort(
                    __event_emitter__,
                    f"MemPalace dry run: would write {len(exchanges)} exchanges",
                    done=True,
                )
            return {
                "success": True,
                "dry_run": True,
                "chat_id": chat_id,
                "exchanges_found": len(exchanges),
                "would_write": len(exchanges),
            }

        try:
            tool_add_drawer = self._mcp_server().tool_add_drawer
        except Exception as exc:
            return {"success": False, "error": f"Failed to import MemPalace: {exc}"}

        try:
            with _owui_mp_write_lock(**self._write_lock_kwargs()):
                for user_msg, assistant_msg in exchanges:
                    user_id = self._uri_part(user_msg.get("id") or self._hash_message(user_msg))
                    assistant_id = self._uri_part(assistant_msg.get("id") or self._hash_message(assistant_msg))
                    source_file = f"open-webui://chat/{chat_uri_id}/exchange/{user_id}-{assistant_id}"
                    content = self._exchange_content(chat_id, user_msg, assistant_msg)

                    try:
                        result = tool_add_drawer(
                            wing=self.valves.default_wing,
                            room=self.valves.default_room,
                            content=content,
                            source_file=source_file,
                            added_by=self._added_by(__user__),
                        )
                        if result.get("success"):
                            if result.get("reason") == "already_exists":
                                skipped += 1
                            else:
                                imported += 1
                        else:
                            errors.append(str(result.get("error") or result))
                    except Exception as exc:
                        errors.append(str(exc))
        except _OwuiMpLockUnavailable as exc:
            return {"success": False, "error": str(exc)}

        if __event_emitter__:
            await self._emit_best_effort(
                __event_emitter__,
                f"MemPalace: imported {imported}, skipped {skipped}, errors {len(errors)}",
                done=True,
            )

        return {
            "success": len(errors) == 0,
            "chat_id": chat_id,
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pair_exchanges(self, messages: list[dict]) -> list[tuple[dict, dict]]:
        pairs: list[tuple[dict, dict]] = []
        pending_user: Optional[dict] = None
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role == "user":
                pending_user = msg
            elif role == "assistant" and pending_user is not None:
                pairs.append((pending_user, msg))
                pending_user = None
        return pairs

    def _content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    elif "text" in item:
                        parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part)
        return str(content or "")

    def _exchange_content(self, chat_id: str, user_msg: dict, assistant_msg: dict) -> str:
        user_text = self._content_to_text(user_msg.get("content", "")).strip()
        assistant_text = self._content_to_text(assistant_msg.get("content", "")).strip()
        content = (
            f"Open WebUI chat exchange\n"
            f"chat_id: {chat_id}\n"
            f"user_message_id: {user_msg.get('id', '')}\n"
            f"assistant_message_id: {assistant_msg.get('id', '')}\n"
            f"user_timestamp: {user_msg.get('timestamp', '')}\n"
            f"assistant_timestamp: {assistant_msg.get('timestamp', '')}\n"
            f"\nUSER:\n{user_text}\n\nASSISTANT:\n{assistant_text}"
        )
        return content[: int(self.valves.max_exchange_chars)]

    def _hash_message(self, msg: dict) -> str:
        h = hashlib.sha256()
        h.update(str(msg.get("role", "")).encode())
        h.update(self._content_to_text(msg.get("content", "")).encode())
        return h.hexdigest()[:16]

    def _added_by(self, __user__: Optional[dict]) -> str:
        user_id = "unknown"
        if isinstance(__user__, dict):
            user_id = str(__user__.get("id") or __user__.get("email") or "unknown")
        return f"open-webui-action:{user_id}"

    async def _emit(self, emitter: Any, description: str, done: bool) -> None:
        await emitter({"type": "status", "data": {"description": description, "done": done}})

    async def _emit_best_effort(self, emitter: Any, description: str, done: bool) -> None:
        try:
            await self._emit(emitter, description, done)
        except Exception:
            pass

    def _uri_part(self, value: Any) -> str:
        return quote(str(value), safe="")
