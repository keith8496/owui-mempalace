"""
title: MemPalace Tools
author: Keith
version: 0.1.0
description: Open WebUI tools wrapping MemPalace Python handlers.
requirements: mempalace>=3.3.5

Open WebUI Tools: MemPalace

Upload this file as an Open WebUI Tool plugin.

The implementation intentionally wraps MemPalace's Python MCP handler functions
instead of speaking stdio MCP. That keeps the first integration small and avoids
transport/process lifecycle work.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

# [[[INJECT:OWUI_MEMPALACE_SHARED_LOCK]]]

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - Open WebUI normally provides pydantic
    BaseModel = object  # type: ignore

    def Field(default=None, **_: Any):  # type: ignore
        return default


class Valves(BaseModel):
    """Admin-level configuration for the MemPalace tool plugin."""

    enable_write_tools: bool = Field(
        default=True,
        description="Allow tools that add/update memories. Disable for read-only deployments.",
    )
    enable_update_tools: bool = Field(
        default=False,
        description="Allow updating existing drawers. Disabled by default.",
    )
    enable_delete_tools: bool = Field(
        default=False,
        description="Allow destructive delete operations. Disabled by default.",
    )
    enable_kg_tools: bool = Field(
        default=False,
        description=(
            "Expose MemPalace knowledge graph tools. Disabled by default until "
            "MemPalace KG storage honors MEMPALACE_PALACE_PATH for direct imports."
        ),
    )
    max_search_results: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum result count a model may request from search/list operations.",
    )
    default_added_by_prefix: str = Field(
        default="open-webui",
        description="Prefix used in MemPalace metadata for Open WebUI-originated writes.",
    )
    palace_path: str = Field(
        default="/app/backend/data/mempalace",
        description="MemPalace palace directory for Open WebUI persistent storage.",
    )
    use_redis_write_lock: bool = Field(
        default=False,
        description="Serialize MemPalace writes across OWUI workers with Redis.",
    )
    redis_lock_ttl_seconds: int = Field(default=120, ge=1, le=3600)
    redis_lock_wait_seconds: int = Field(default=10, ge=0, le=120)


class Tools:
    def __init__(self) -> None:
        self.valves = Valves()

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _ensure_palace_path(self) -> None:
        """Set the MemPalace palace path before the lazy runtime import."""
        palace_path = str(getattr(self.valves, "palace_path", "") or "").strip()
        if palace_path and not os.environ.get("MEMPALACE_PALACE_PATH", "").strip():
            os.environ["MEMPALACE_PALACE_PATH"] = palace_path

    def _mcp_server(self):
        self._ensure_palace_path()
        from mempalace import mcp_server

        return mcp_server

    def _clamp_limit(self, limit: int, default: int = 5) -> int:
        try:
            value = int(limit)
        except Exception:
            value = default
        return max(1, min(value, int(self.valves.max_search_results)))

    def _added_by(self, __user__: Optional[dict]) -> str:
        user_id = "unknown"
        if isinstance(__user__, dict):
            user_id = str(__user__.get("id") or __user__.get("email") or "unknown")
        return f"{self.valves.default_added_by_prefix}:{user_id}"

    def _source_uri(self, __metadata__: Optional[dict], fallback: str = "manual") -> str:
        metadata = __metadata__ if isinstance(__metadata__, dict) else {}
        chat_id = self._uri_part(metadata.get("chat_id") or "unknown")
        message_id = self._uri_part(metadata.get("message_id") or metadata.get("id") or fallback)
        return f"open-webui://chat/{chat_id}/message/{message_id}"

    def _uri_part(self, value: Any) -> str:
        return quote(str(value), safe="")

    def _write_lock_kwargs(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.valves.use_redis_write_lock),
            "palace_path": str(self.valves.palace_path),
            "ttl_seconds": int(self.valves.redis_lock_ttl_seconds),
            "wait_seconds": int(self.valves.redis_lock_wait_seconds),
            "key_prefix": (os.environ.get("REDIS_KEY_PREFIX") or "open-webui").strip() or "open-webui",
        }

    # ---------------------------------------------------------------------
    # Read tools
    # ---------------------------------------------------------------------

    def mempalace_status(self) -> dict:
        """Return MemPalace status, including drawer counts and health information."""
        return self._mcp_server().tool_status()

    def mempalace_list_wings(self) -> dict:
        """List all MemPalace wings with drawer counts."""
        return self._mcp_server().tool_list_wings()

    def mempalace_list_rooms(self, wing: Optional[str] = None) -> dict:
        """List MemPalace rooms, optionally scoped to a wing."""
        return self._mcp_server().tool_list_rooms(wing=wing)

    def mempalace_get_taxonomy(self) -> dict:
        """Return the full MemPalace wing -> room -> count taxonomy."""
        return self._mcp_server().tool_get_taxonomy()

    def mempalace_search(
        self,
        query: str,
        limit: int = 5,
        wing: Optional[str] = None,
        room: Optional[str] = None,
        max_distance: float = 1.5,
        context: Optional[str] = None,
    ) -> dict:
        """Search MemPalace memories semantically.

        Keep query short and focused. Use wing and room filters when known.
        """
        return self._mcp_server().tool_search(
            query=query,
            limit=self._clamp_limit(limit),
            wing=wing,
            room=room,
            max_distance=max_distance,
            context=context,
        )

    def mempalace_check_duplicate(self, content: str, threshold: float = 0.9) -> dict:
        """Check whether similar content already exists in MemPalace."""
        return self._mcp_server().tool_check_duplicate(content=content, threshold=threshold)

    def mempalace_get_drawer(self, drawer_id: str) -> dict:
        """Fetch a single MemPalace drawer by ID."""
        return self._mcp_server().tool_get_drawer(drawer_id=drawer_id)

    def mempalace_list_drawers(
        self,
        wing: Optional[str] = None,
        room: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """List MemPalace drawers with optional wing/room filters and pagination."""
        return self._mcp_server().tool_list_drawers(
            wing=wing,
            room=room,
            limit=self._clamp_limit(limit, default=20),
            offset=max(0, int(offset or 0)),
        )

    # ---------------------------------------------------------------------
    # Write tools
    # ---------------------------------------------------------------------

    def mempalace_add_drawer(
        self,
        wing: str,
        room: str,
        content: str,
        source_file: Optional[str] = None,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        """Store verbatim content in MemPalace under a wing and room."""
        if not self.valves.enable_write_tools:
            return {"success": False, "error": "MemPalace write tools are disabled"}

        try:
            with _owui_mp_write_lock(**self._write_lock_kwargs()):
                return self._mcp_server().tool_add_drawer(
                    wing=wing,
                    room=room,
                    content=content,
                    source_file=source_file or self._source_uri(__metadata__),
                    added_by=self._added_by(__user__),
                )
        except _OwuiMpLockUnavailable as exc:
            return {"success": False, "error": str(exc)}

    def mempalace_update_drawer(
        self,
        drawer_id: str,
        content: Optional[str] = None,
        wing: Optional[str] = None,
        room: Optional[str] = None,
    ) -> dict:
        """Update an existing drawer's content and/or wing/room metadata."""
        if not self.valves.enable_write_tools:
            return {"success": False, "error": "MemPalace write tools are disabled"}
        if not self.valves.enable_update_tools:
            return {"success": False, "error": "MemPalace update tools are disabled"}

        try:
            with _owui_mp_write_lock(**self._write_lock_kwargs()):
                return self._mcp_server().tool_update_drawer(drawer_id=drawer_id, content=content, wing=wing, room=room)
        except _OwuiMpLockUnavailable as exc:
            return {"success": False, "error": str(exc)}

    def mempalace_delete_drawer(self, drawer_id: str) -> dict:
        """Delete a MemPalace drawer by ID. This is irreversible and disabled by default."""
        if not self.valves.enable_delete_tools:
            return {"success": False, "error": "MemPalace delete tools are disabled"}

        try:
            with _owui_mp_write_lock(**self._write_lock_kwargs()):
                return self._mcp_server().tool_delete_drawer(drawer_id=drawer_id)
        except _OwuiMpLockUnavailable as exc:
            return {"success": False, "error": str(exc)}

    # ---------------------------------------------------------------------
    # Diary tools
    # ---------------------------------------------------------------------

    def mempalace_diary_write(
        self,
        entry: str,
        topic: str = "general",
        wing: Optional[str] = None,
        agent_name: str = "open-webui",
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        """Write a compressed diary/checkpoint entry to MemPalace."""
        if not self.valves.enable_write_tools:
            return {"success": False, "error": "MemPalace write tools are disabled"}

        # Include minimal provenance in the entry rather than relying only on metadata.
        source = self._source_uri(__metadata__, fallback="diary")
        user_id = (__user__ or {}).get("id", "unknown") if isinstance(__user__, dict) else "unknown"
        enriched = f"{entry}\nSRC:{source}|USER:{user_id}"
        try:
            with _owui_mp_write_lock(**self._write_lock_kwargs()):
                return self._mcp_server().tool_diary_write(agent_name=agent_name, entry=enriched, topic=topic, wing=wing)
        except _OwuiMpLockUnavailable as exc:
            return {"success": False, "error": str(exc)}

    def mempalace_diary_read(
        self,
        agent_name: str = "open-webui",
        limit: int = 10,
        wing: Optional[str] = None,
    ) -> dict:
        """Read recent MemPalace diary entries for an agent."""
        return self._mcp_server().tool_diary_read(agent_name=agent_name, limit=self._clamp_limit(limit), wing=wing)

    # ---------------------------------------------------------------------
    # Knowledge graph tools
    # ---------------------------------------------------------------------

    def mempalace_kg_query(
        self,
        entity: str,
        as_of: Optional[str] = None,
        direction: str = "both",
    ) -> dict:
        """Query MemPalace knowledge graph facts for an entity."""
        if not self.valves.enable_kg_tools:
            return {"error": "MemPalace knowledge graph tools are disabled"}

        return self._mcp_server().tool_kg_query(entity=entity, as_of=as_of, direction=direction)

    def mempalace_kg_add(
        self,
        subject: str,
        predicate: str,
        object: str,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
        source_file: Optional[str] = None,
        source_drawer_id: Optional[str] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        """Add a subject-predicate-object fact to the MemPalace knowledge graph."""
        if not self.valves.enable_write_tools:
            return {"success": False, "error": "MemPalace write tools are disabled"}
        if not self.valves.enable_kg_tools:
            return {"success": False, "error": "MemPalace knowledge graph tools are disabled"}

        try:
            with _owui_mp_write_lock(**self._write_lock_kwargs()):
                return self._mcp_server().tool_kg_add(
                    subject=subject,
                    predicate=predicate,
                    object=object,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    source_file=source_file or self._source_uri(__metadata__, fallback="kg"),
                    source_drawer_id=source_drawer_id,
                )
        except _OwuiMpLockUnavailable as exc:
            return {"success": False, "error": str(exc)}

    def mempalace_kg_invalidate(
        self,
        subject: str,
        predicate: str,
        object: str,
        ended: Optional[str] = None,
    ) -> dict:
        """Mark a MemPalace knowledge graph fact as no longer true."""
        if not self.valves.enable_write_tools:
            return {"success": False, "error": "MemPalace write tools are disabled"}
        if not self.valves.enable_kg_tools:
            return {"success": False, "error": "MemPalace knowledge graph tools are disabled"}

        try:
            with _owui_mp_write_lock(**self._write_lock_kwargs()):
                return self._mcp_server().tool_kg_invalidate(subject=subject, predicate=predicate, object=object, ended=ended)
        except _OwuiMpLockUnavailable as exc:
            return {"success": False, "error": str(exc)}

    def mempalace_kg_timeline(self, entity: Optional[str] = None) -> dict:
        """Return chronological knowledge graph facts, optionally for one entity."""
        if not self.valves.enable_kg_tools:
            return {"error": "MemPalace knowledge graph tools are disabled"}

        return self._mcp_server().tool_kg_timeline(entity=entity)

    def mempalace_kg_stats(self) -> dict:
        """Return MemPalace knowledge graph statistics."""
        if not self.valves.enable_kg_tools:
            return {"error": "MemPalace knowledge graph tools are disabled"}

        return self._mcp_server().tool_kg_stats()
