"""
Open WebUI Filter: MemPalace recall and optional checkpoint harvesting.

Upload this file as an Open WebUI Filter function.

Default behavior:
- inlet recall is enabled;
- outlet harvesting is disabled;
- assistant/user messages are not modified except for adding a compact recall
  block before model generation.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Optional
from urllib.parse import quote

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore

    def Field(default=None, **_: Any):  # type: ignore
        return default


class Valves(BaseModel):
    enable_recall: bool = Field(default=True, description="Search MemPalace before each chat turn.")
    recall_limit: int = Field(default=5, ge=1, le=20, description="Maximum recalled memories.")
    recall_max_chars: int = Field(default=4000, ge=500, le=20000, description="Recall block cap.")
    recall_max_distance: float = Field(default=1.5, description="MemPalace cosine distance cutoff.")
    recall_wing: str = Field(default="", description="Optional wing filter for recall.")
    recall_room: str = Field(default="", description="Optional room filter for recall.")
    inject_mode: str = Field(default="system", description="system or first_user.")

    enable_harvest: bool = Field(default=False, description="Enable outlet checkpoint harvesting.")
    harvest_interval_user_messages: int = Field(default=15, ge=1, le=100)
    harvest_wing: str = Field(default="open_webui", description="Wing for automatic checkpoints.")
    harvest_room: str = Field(default="checkpoints", description="Room for automatic checkpoints.")
    harvest_max_chars: int = Field(default=12000, ge=1000, le=50000)


class Filter:
    def __init__(self) -> None:
        self.valves = Valves()

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        **_: Any,
    ) -> dict:
        """Inject compact MemPalace recall into the prompt before model generation."""
        if not self.valves.enable_recall:
            return body

        messages = body.get("messages") or []
        if not isinstance(messages, list):
            return body

        last_user = self._last_message_by_role(messages, "user")
        if not last_user:
            return body

        query = self._content_to_text(last_user.get("content", "")).strip()[:250]
        if not query:
            return body

        try:
            from mempalace.mcp_server import tool_search

            result = tool_search(
                query=query,
                limit=max(1, int(self.valves.recall_limit)),
                wing=self.valves.recall_wing or None,
                room=self.valves.recall_room or None,
                max_distance=float(self.valves.recall_max_distance),
                context="Open WebUI automatic inlet recall",
            )
        except Exception as exc:
            # Fail open: memory recall must not break chat completion.
            body.setdefault("metadata", {})["mempalace_recall_error"] = str(exc)
            return body

        recall_text = self._format_search_results(result)
        if not recall_text:
            return body

        block = (
            "Relevant MemPalace memories retrieved automatically. "
            "Treat these as fallible recalled context, not guaranteed truth.\n\n"
            f"{recall_text}"
        )[: int(self.valves.recall_max_chars)]

        if self.valves.inject_mode == "first_user":
            last_user["content"] = f"{block}\n\nCurrent user message:\n{self._content_to_text(last_user.get('content', ''))}"
        else:
            self._add_or_append_system_message(messages, block)

        return body

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Any = None,
        **_: Any,
    ) -> dict:
        """Optionally checkpoint completed chats after a configured number of user messages."""
        if not self.valves.enable_harvest:
            return body

        messages = body.get("messages") or []
        if not isinstance(messages, list):
            return body

        user_count = sum(1 for msg in messages if msg.get("role") == "user")
        interval = max(1, int(self.valves.harvest_interval_user_messages))
        if user_count == 0 or user_count % interval != 0:
            return body

        assistant = self._last_message_by_role(messages, "assistant")
        if not assistant:
            return body

        chat_id = self._uri_part(body.get("chat_id") or (__metadata__ or {}).get("chat_id") or "unknown")
        assistant_id = self._uri_part(assistant.get("id") or body.get("id") or self._hash_messages(messages))
        source_file = f"open-webui://chat/{chat_id}/checkpoint/{assistant_id}"
        content = self._checkpoint_content(chat_id, user_count, messages)

        try:
            from mempalace.mcp_server import tool_add_drawer

            result = tool_add_drawer(
                wing=self.valves.harvest_wing,
                room=self.valves.harvest_room,
                content=content,
                source_file=source_file,
                added_by=self._added_by(__user__),
            )
            if __event_emitter__:
                try:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": f"MemPalace checkpoint: {result.get('reason') or result.get('drawer_id') or result}",
                                "done": True,
                            },
                        }
                    )
                except Exception:
                    pass
        except Exception as exc:
            # Fail open and preserve the generated answer.
            body.setdefault("metadata", {})["mempalace_harvest_error"] = str(exc)

        return body

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _last_message_by_role(self, messages: list[dict], role: str) -> Optional[dict]:
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == role:
                return msg
        return None

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

    def _format_search_results(self, result: dict) -> str:
        if not isinstance(result, dict) or result.get("error"):
            return ""

        candidates = result.get("results") or result.get("matches") or result.get("memories") or []
        lines: list[str] = []

        if isinstance(candidates, list):
            for idx, item in enumerate(candidates[: int(self.valves.recall_limit)], start=1):
                if not isinstance(item, dict):
                    continue
                content = (
                    item.get("content")
                    or item.get("document")
                    or item.get("text")
                    or item.get("preview")
                    or ""
                )
                if not content:
                    continue
                wing = item.get("wing") or item.get("metadata", {}).get("wing", "?")
                room = item.get("room") or item.get("metadata", {}).get("room", "?")
                score = item.get("similarity") or item.get("distance") or item.get("score")
                score_text = f" score={score}" if score is not None else ""
                lines.append(f"{idx}. [{wing}/{room}{score_text}] {str(content).strip()[:900]}")

        # Some MemPalace versions may return formatted text rather than a list.
        if not lines:
            text = result.get("text") or result.get("output") or result.get("formatted")
            if isinstance(text, str):
                return text.strip()[: int(self.valves.recall_max_chars)]

        return "\n".join(lines)[: int(self.valves.recall_max_chars)]

    def _add_or_append_system_message(self, messages: list[dict], block: str) -> None:
        for msg in messages:
            if msg.get("role") == "system":
                current = self._content_to_text(msg.get("content", ""))
                msg["content"] = f"{current}\n\n{block}" if current else block
                return
        messages.insert(0, {"role": "system", "content": block})

    def _checkpoint_content(self, chat_id: str, user_count: int, messages: list[dict]) -> str:
        recent = messages[-10:]
        lines = [
            f"Open WebUI MemPalace checkpoint",
            f"chat_id: {chat_id}",
            f"user_messages: {user_count}",
            f"created_at: {datetime.now(UTC).isoformat()}",
            "",
        ]
        for msg in recent:
            role = msg.get("role", "unknown")
            text = self._content_to_text(msg.get("content", "")).strip()
            if text:
                lines.append(f"{role.upper()}:\n{text}\n")
        return "\n".join(lines)[: int(self.valves.harvest_max_chars)]

    def _hash_messages(self, messages: list[dict]) -> str:
        h = hashlib.sha256()
        for msg in messages[-4:]:
            h.update(str(msg.get("id", "")).encode())
            h.update(self._content_to_text(msg.get("content", "")).encode())
        return h.hexdigest()[:16]

    def _added_by(self, __user__: Optional[dict]) -> str:
        user_id = "unknown"
        if isinstance(__user__, dict):
            user_id = str(__user__.get("id") or __user__.get("email") or "unknown")
        return f"open-webui-filter:{user_id}"

    def _uri_part(self, value: Any) -> str:
        return quote(str(value), safe="")
