"""Shared test fixtures for OWUI MemPalace plugins.

The plugin files import MemPalace lazily from method bodies. Tests install a
fake `mempalace.mcp_server` module so they enforce wrapper behavior without
requiring chromadb or a real palace on the test machine.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class FakeMempalaceCalls:
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def record(self, name: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((name, kwargs))
        if name == "tool_search":
            return {
                "results": [
                    {
                        "content": "OWUI can call MemPalace Python handlers directly.",
                        "wing": "open_webui",
                        "room": "integration",
                        "similarity": 0.82,
                    },
                    {
                        "content": "Automatic recall should be fallible and compact.",
                        "metadata": {"wing": "open_webui", "room": "recall"},
                        "distance": 0.25,
                    },
                ]
            }
        if name == "tool_add_drawer":
            return {
                "success": True,
                "drawer_id": f"drawer_{len(self.calls)}",
                **kwargs,
            }
        if name == "tool_status":
            return {"drawers": 3, "ok": True}
        if name == "tool_check_duplicate":
            return {"is_duplicate": False, "matches": []}
        if name == "tool_diary_write":
            return {"success": True, "entry_id": "diary_1", **kwargs}
        if name == "tool_diary_read":
            return {"entries": [], **kwargs}
        if name.startswith("tool_kg_"):
            return {"success": True, "tool": name, **kwargs}
        if name.startswith("tool_list") or name.startswith("tool_get"):
            return {"success": True, "tool": name, **kwargs}
        if name.startswith("tool_update") or name.startswith("tool_delete"):
            return {"success": True, "tool": name, **kwargs}
        return {"success": True, **kwargs}

    def by_name(self, name: str) -> list[dict[str, Any]]:
        return [kwargs for call_name, kwargs in self.calls if call_name == name]


@pytest.fixture
def fake_mempalace(monkeypatch: pytest.MonkeyPatch) -> FakeMempalaceCalls:
    calls = FakeMempalaceCalls()
    package = types.ModuleType("mempalace")
    server = types.ModuleType("mempalace.mcp_server")

    def make_tool(name: str):
        def tool(**kwargs: Any):
            return calls.record(name, **kwargs)

        return tool

    # Read tools.
    server.tool_status = make_tool("tool_status")
    server.tool_list_wings = make_tool("tool_list_wings")
    server.tool_list_rooms = make_tool("tool_list_rooms")
    server.tool_get_taxonomy = make_tool("tool_get_taxonomy")
    server.tool_search = make_tool("tool_search")
    server.tool_check_duplicate = make_tool("tool_check_duplicate")
    server.tool_get_drawer = make_tool("tool_get_drawer")
    server.tool_list_drawers = make_tool("tool_list_drawers")

    # Write tools.
    server.tool_add_drawer = make_tool("tool_add_drawer")
    server.tool_update_drawer = make_tool("tool_update_drawer")
    server.tool_delete_drawer = make_tool("tool_delete_drawer")

    # Diary tools.
    server.tool_diary_write = make_tool("tool_diary_write")
    server.tool_diary_read = make_tool("tool_diary_read")

    # KG tools.
    server.tool_kg_query = make_tool("tool_kg_query")
    server.tool_kg_add = make_tool("tool_kg_add")
    server.tool_kg_invalidate = make_tool("tool_kg_invalidate")
    server.tool_kg_timeline = make_tool("tool_kg_timeline")
    server.tool_kg_stats = make_tool("tool_kg_stats")

    package.mcp_server = server
    monkeypatch.setitem(sys.modules, "mempalace", package)
    monkeypatch.setitem(sys.modules, "mempalace.mcp_server", server)
    return calls


@pytest.fixture
def sample_messages() -> list[dict[str, Any]]:
    return [
        {"id": "u1", "role": "user", "content": "How should OWUI integrate with MemPalace?", "timestamp": 1},
        {"id": "a1", "role": "assistant", "content": "Use Python handlers directly.", "timestamp": 2},
        {"id": "u2", "role": "user", "content": "How do we harvest chats?", "timestamp": 3},
        {"id": "a2", "role": "assistant", "content": "Use explicit actions first.", "timestamp": 4},
    ]


@pytest.fixture
def event_emitter():
    events: list[dict[str, Any]] = []

    async def emit(event: dict[str, Any]) -> None:
        events.append(event)

    emit.events = events  # type: ignore[attr-defined]
    return emit
