from __future__ import annotations

import os

from owui_mempalace_tools import Tools


def test_search_wraps_mempalace_handler_and_clamps_limit(fake_mempalace):
    tools = Tools()
    result = tools.mempalace_search(
        query="Open WebUI MemPalace integration",
        limit=500,
        wing="open_webui",
        room="integration",
        max_distance=1.2,
    )

    assert result["results"]
    call = fake_mempalace.by_name("tool_search")[0]
    assert call == {
        "query": "Open WebUI MemPalace integration",
        "limit": 10,
        "wing": "open_webui",
        "room": "integration",
        "max_distance": 1.2,
        "context": None,
    }


def test_add_drawer_is_valve_gated_before_importing_or_writing(fake_mempalace):
    tools = Tools()
    tools.valves.enable_write_tools = False

    result = tools.mempalace_add_drawer(
        wing="open_webui",
        room="integration",
        content="do not write",
        __user__={"id": "user-1"},
        __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
    )

    assert result == {"success": False, "error": "MemPalace write tools are disabled"}
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_add_drawer_attaches_open_webui_provenance(fake_mempalace):
    tools = Tools()

    result = tools.mempalace_add_drawer(
        wing="open_webui",
        room="integration",
        content="OWUI can call MemPalace Python handlers directly.",
        __user__={"id": "user-1"},
        __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
    )

    assert result["success"] is True
    call = fake_mempalace.by_name("tool_add_drawer")[0]
    assert call["source_file"] == "open-webui://chat/chat-1/message/msg-1"
    assert call["added_by"] == "open-webui:user-1"
    assert call["wing"] == "open_webui"
    assert call["room"] == "integration"


def test_delete_drawer_is_disabled_by_default(fake_mempalace):
    tools = Tools()

    result = tools.mempalace_delete_drawer("drawer-1")

    assert result == {"success": False, "error": "MemPalace delete tools are disabled"}
    assert fake_mempalace.by_name("tool_delete_drawer") == []


def test_kg_tools_are_valve_gated(fake_mempalace):
    tools = Tools()
    tools.valves.enable_kg_tools = False

    query_result = tools.mempalace_kg_query("Open WebUI")
    add_result = tools.mempalace_kg_add("Open WebUI", "uses", "MemPalace")

    assert query_result == {"error": "MemPalace knowledge graph tools are disabled"}
    assert add_result == {"success": False, "error": "MemPalace knowledge graph tools are disabled"}
    assert fake_mempalace.by_name("tool_kg_query") == []
    assert fake_mempalace.by_name("tool_kg_add") == []


def test_diary_write_enriches_entry_with_source_and_user(fake_mempalace):
    tools = Tools()

    result = tools.mempalace_diary_write(
        entry="CHECKPOINT: integration design",
        topic="checkpoint",
        wing="open_webui",
        __user__={"id": "user-1"},
        __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
    )

    assert result["success"] is True
    call = fake_mempalace.by_name("tool_diary_write")[0]
    assert call["agent_name"] == "open-webui"
    assert call["topic"] == "checkpoint"
    assert call["wing"] == "open_webui"
    assert "SRC:open-webui://chat/chat-1/message/msg-1|USER:user-1" in call["entry"]


def test_default_tool_valves_match_safety_design():
    tools = Tools()

    assert tools.valves.enable_write_tools is True
    assert tools.valves.enable_update_tools is False
    assert tools.valves.enable_delete_tools is False
    assert tools.valves.enable_kg_tools is False
    assert tools.valves.palace_path == "/app/backend/data/mempalace"
    assert tools.valves.max_search_results == 10



def test_tools_set_default_palace_path_before_import(fake_mempalace, monkeypatch):
    monkeypatch.delenv("MEMPALACE_PALACE_PATH", raising=False)
    tools = Tools()

    tools.mempalace_status()

    assert os.environ["MEMPALACE_PALACE_PATH"] == "/app/backend/data/mempalace"


def test_tools_preserve_existing_palace_path_env(fake_mempalace, monkeypatch):
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", "/custom/palace")
    tools = Tools()

    tools.mempalace_status()

    assert os.environ["MEMPALACE_PALACE_PATH"] == "/custom/palace"


def test_tools_replace_blank_palace_path_env(fake_mempalace, monkeypatch):
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", "   ")
    tools = Tools()

    tools.mempalace_status()

    assert os.environ["MEMPALACE_PALACE_PATH"] == "/app/backend/data/mempalace"

def test_read_tools_delegate_to_mempalace_handlers(fake_mempalace):
    tools = Tools()

    assert tools.mempalace_status()["drawers"] == 3
    assert tools.mempalace_list_wings()["tool"] == "tool_list_wings"
    assert tools.mempalace_list_rooms(wing="open_webui")["tool"] == "tool_list_rooms"
    assert tools.mempalace_get_taxonomy()["tool"] == "tool_get_taxonomy"

    assert fake_mempalace.by_name("tool_status") == [{}]
    assert fake_mempalace.by_name("tool_list_wings") == [{}]
    assert fake_mempalace.by_name("tool_list_rooms") == [{"wing": "open_webui"}]
    assert fake_mempalace.by_name("tool_get_taxonomy") == [{}]


def test_drawer_read_and_list_helpers_delegate_and_normalize_pagination(fake_mempalace):
    tools = Tools()

    get_result = tools.mempalace_get_drawer("drawer-1")
    list_result = tools.mempalace_list_drawers(
        wing="open_webui",
        room="integration",
        limit=999,
        offset=-50,
    )

    assert get_result["tool"] == "tool_get_drawer"
    assert list_result["tool"] == "tool_list_drawers"
    assert fake_mempalace.by_name("tool_get_drawer") == [{"drawer_id": "drawer-1"}]
    assert fake_mempalace.by_name("tool_list_drawers") == [
        {"wing": "open_webui", "room": "integration", "limit": 10, "offset": 0}
    ]


def test_check_duplicate_delegates_threshold(fake_mempalace):
    tools = Tools()

    result = tools.mempalace_check_duplicate("same memory", threshold=0.75)

    assert result == {"is_duplicate": False, "matches": []}
    assert fake_mempalace.by_name("tool_check_duplicate") == [
        {"content": "same memory", "threshold": 0.75}
    ]


def test_update_drawer_gated_and_success_path(fake_mempalace):
    tools = Tools()
    tools.valves.enable_write_tools = False

    blocked = tools.mempalace_update_drawer("drawer-1", content="new")
    assert blocked == {"success": False, "error": "MemPalace write tools are disabled"}
    assert fake_mempalace.by_name("tool_update_drawer") == []

    tools.valves.enable_write_tools = True
    still_blocked = tools.mempalace_update_drawer("drawer-1", content="new")
    assert still_blocked == {"success": False, "error": "MemPalace update tools are disabled"}
    assert fake_mempalace.by_name("tool_update_drawer") == []

    tools.valves.enable_update_tools = True
    result = tools.mempalace_update_drawer(
        "drawer-1",
        content="new content",
        wing="open_webui",
        room="decisions",
    )

    assert result["tool"] == "tool_update_drawer"
    assert fake_mempalace.by_name("tool_update_drawer") == [
        {"drawer_id": "drawer-1", "content": "new content", "wing": "open_webui", "room": "decisions"}
    ]


def test_delete_drawer_success_path_when_explicitly_enabled(fake_mempalace):
    tools = Tools()
    tools.valves.enable_delete_tools = True

    result = tools.mempalace_delete_drawer("drawer-1")

    assert result["tool"] == "tool_delete_drawer"
    assert fake_mempalace.by_name("tool_delete_drawer") == [{"drawer_id": "drawer-1"}]


def test_diary_read_delegates_and_clamps_limit(fake_mempalace):
    tools = Tools()

    result = tools.mempalace_diary_read(agent_name="open-webui", limit=999, wing="open_webui")

    assert result["entries"] == []
    assert fake_mempalace.by_name("tool_diary_read") == [
        {"agent_name": "open-webui", "limit": 10, "wing": "open_webui"}
    ]


def test_source_uri_fallbacks_and_explicit_source_override(fake_mempalace):
    tools = Tools()

    tools.mempalace_add_drawer("open_webui", "integration", "no metadata")
    tools.mempalace_add_drawer(
        "open_webui",
        "integration",
        "metadata id",
        __metadata__={"chat_id": "chat-1", "id": "body-msg"},
    )
    tools.mempalace_add_drawer(
        "open_webui",
        "integration",
        "explicit source",
        source_file="manual://source",
        __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
    )

    calls = fake_mempalace.by_name("tool_add_drawer")
    assert calls[0]["source_file"] == "open-webui://chat/unknown/message/manual"
    assert calls[1]["source_file"] == "open-webui://chat/chat-1/message/body-msg"
    assert calls[2]["source_file"] == "manual://source"


def test_added_by_fallbacks(fake_mempalace):
    tools = Tools()

    tools.mempalace_add_drawer("open_webui", "integration", "unknown user")
    tools.mempalace_add_drawer(
        "open_webui",
        "integration",
        "email user",
        __user__={"email": "user@example.com"},
    )

    calls = fake_mempalace.by_name("tool_add_drawer")
    assert calls[0]["added_by"] == "open-webui:unknown"
    assert calls[1]["added_by"] == "open-webui:user@example.com"


def test_kg_happy_paths_and_source_fallbacks(fake_mempalace):
    tools = Tools()
    tools.valves.enable_kg_tools = True

    query = tools.mempalace_kg_query("Open WebUI", as_of="2026-05-20", direction="outgoing")
    add = tools.mempalace_kg_add(
        "Open WebUI",
        "uses",
        "MemPalace",
        valid_from="2026-05-20",
        __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
    )
    invalidate = tools.mempalace_kg_invalidate("Open WebUI", "used", "old memory", ended="2026-05-20")
    timeline = tools.mempalace_kg_timeline("Open WebUI")
    stats = tools.mempalace_kg_stats()

    assert query["tool"] == "tool_kg_query"
    assert add["tool"] == "tool_kg_add"
    assert invalidate["tool"] == "tool_kg_invalidate"
    assert timeline["tool"] == "tool_kg_timeline"
    assert stats["tool"] == "tool_kg_stats"
    assert fake_mempalace.by_name("tool_kg_add")[0]["source_file"] == "open-webui://chat/chat-1/message/msg-1"


def test_kg_add_write_gate_takes_precedence(fake_mempalace):
    tools = Tools()
    tools.valves.enable_write_tools = False
    tools.valves.enable_kg_tools = False

    result = tools.mempalace_kg_add("Open WebUI", "uses", "MemPalace")

    assert result == {"success": False, "error": "MemPalace write tools are disabled"}
    assert fake_mempalace.by_name("tool_kg_add") == []



def test_diary_write_is_write_gated(fake_mempalace):
    tools = Tools()
    tools.valves.enable_write_tools = False

    result = tools.mempalace_diary_write("do not write")

    assert result == {"success": False, "error": "MemPalace write tools are disabled"}
    assert fake_mempalace.by_name("tool_diary_write") == []


def test_kg_invalidate_is_write_gated(fake_mempalace):
    tools = Tools()
    tools.valves.enable_write_tools = False
    tools.valves.enable_kg_tools = True

    result = tools.mempalace_kg_invalidate("Open WebUI", "uses", "MemPalace")

    assert result == {"success": False, "error": "MemPalace write tools are disabled"}
    assert fake_mempalace.by_name("tool_kg_invalidate") == []


def test_kg_add_gate_matrix(fake_mempalace):
    tools = Tools()

    tools.valves.enable_write_tools = False
    tools.valves.enable_kg_tools = True
    assert tools.mempalace_kg_add("s", "p", "o") == {
        "success": False,
        "error": "MemPalace write tools are disabled",
    }

    tools.valves.enable_write_tools = True
    tools.valves.enable_kg_tools = False
    assert tools.mempalace_kg_add("s", "p", "o") == {
        "success": False,
        "error": "MemPalace knowledge graph tools are disabled",
    }

    tools.valves.enable_write_tools = True
    tools.valves.enable_kg_tools = True
    assert tools.mempalace_kg_add("s", "p", "o")["tool"] == "tool_kg_add"


def test_tool_source_uri_encodes_chat_and_message_ids(fake_mempalace):
    tools = Tools()

    tools.mempalace_add_drawer(
        "open_webui",
        "integration",
        "encoded ids",
        __metadata__={"chat_id": "folder/chat 1", "message_id": "msg/1"},
    )

    call = fake_mempalace.by_name("tool_add_drawer")[0]
    assert call["source_file"] == "open-webui://chat/folder%2Fchat%201/message/msg%2F1"


def test_explicit_tool_runtime_dependency_missing_raises(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name.startswith("mempalace"):
            raise ModuleNotFoundError("blocked mempalace")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    tools = Tools()

    try:
        tools.mempalace_status()
    except ModuleNotFoundError as exc:
        assert "blocked mempalace" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected missing MemPalace dependency to raise")
