"""
Open WebUI Action: Save current chat to MemPalace.

Upload this file as an Open WebUI Action function.

This action is intentionally conservative. It harvests the message list passed
by Open WebUI to the action, pairs user/assistant exchanges, and stores each
exchange as a MemPalace drawer with deterministic Open WebUI provenance.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional
from urllib.parse import quote

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore

    def Field(default=None, **_: Any):  # type: ignore
        return default


class Valves(BaseModel):
    default_wing: str = Field(default="open_webui", description="Wing used for harvested chats.")
    default_room: str = Field(default="conversations", description="Room used for exchange drawers.")
    dry_run: bool = Field(default=False, description="Preview counts without writing to MemPalace.")
    max_exchanges: int = Field(default=100, ge=1, le=1000, description="Maximum exchanges per action run.")
    max_exchange_chars: int = Field(default=20000, ge=1000, le=100000)


class Action:
    def __init__(self) -> None:
        self.valves = Valves()

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
            from mempalace.mcp_server import tool_add_drawer
        except Exception as exc:
            return {"success": False, "error": f"Failed to import MemPalace: {exc}"}

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
