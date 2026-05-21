from __future__ import annotations

import asyncio

from owui_mempalace_filter import Filter


def run(coro):
    return asyncio.run(coro)


def test_inlet_injects_fallible_recall_as_system_context(fake_mempalace):
    filt = Filter()
    body = {"messages": [{"role": "user", "content": "How do we integrate OWUI with MP?"}]}

    result = run(filt.inlet(body, __metadata__={"chat_id": "chat-1"}))

    call = fake_mempalace.by_name("tool_search")[0]
    assert call["query"] == "How do we integrate OWUI with MP?"
    assert call["limit"] == 5
    assert call["context"] == "Open WebUI automatic inlet recall"
    assert result["messages"][0]["role"] == "system"
    assert "Treat these as fallible recalled context" in result["messages"][0]["content"]
    assert "OWUI can call MemPalace Python handlers directly" in result["messages"][0]["content"]


def test_inlet_can_be_disabled_without_searching(fake_mempalace):
    filt = Filter()
    filt.valves.enable_recall = False
    body = {"messages": [{"role": "user", "content": "No recall"}]}

    result = run(filt.inlet(body))

    assert result is body
    assert fake_mempalace.by_name("tool_search") == []
    assert result["messages"] == [{"role": "user", "content": "No recall"}]


def test_inlet_fail_open_records_error_without_breaking_chat(monkeypatch):
    filt = Filter()
    body = {"messages": [{"role": "user", "content": "trigger recall"}]}

    import types
    import sys

    package = types.ModuleType("mempalace")
    server = types.ModuleType("mempalace.mcp_server")

    def boom(**kwargs):
        raise RuntimeError("chroma cold start failed")

    server.tool_search = boom
    package.mcp_server = server
    monkeypatch.setitem(sys.modules, "mempalace", package)
    monkeypatch.setitem(sys.modules, "mempalace.mcp_server", server)

    result = run(filt.inlet(body))

    assert result is body
    assert result["metadata"]["mempalace_recall_error"] == "chroma cold start failed"
    assert result["messages"] == [{"role": "user", "content": "trigger recall"}]


def test_inlet_first_user_mode_does_not_create_system_message(fake_mempalace):
    filt = Filter()
    filt.valves.inject_mode = "first_user"
    body = {"messages": [{"role": "user", "content": "Need recall inline"}]}

    result = run(filt.inlet(body))

    assert len(result["messages"]) == 1
    assert result["messages"][0]["role"] == "user"
    assert "Relevant MemPalace memories" in result["messages"][0]["content"]
    assert "Current user message:\nNeed recall inline" in result["messages"][0]["content"]


def test_outlet_harvesting_disabled_by_default_preserves_body(fake_mempalace, sample_messages):
    filt = Filter()
    body = {"chat_id": "chat-1", "messages": list(sample_messages)}

    result = run(filt.outlet(body, __user__={"id": "user-1"}))

    assert result is body
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_outlet_checkpoint_uses_interval_and_stable_source(fake_mempalace, sample_messages):
    filt = Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 2
    body = {"chat_id": "chat-1", "id": "a2", "messages": list(sample_messages)}

    result = run(filt.outlet(body, __user__={"id": "user-1"}))

    assert result is body
    call = fake_mempalace.by_name("tool_add_drawer")[0]
    assert call["wing"] == "open_webui"
    assert call["room"] == "checkpoints"
    assert call["source_file"] == "open-webui://chat/chat-1/checkpoint/a2"
    assert call["added_by"] == "open-webui-filter:user-1"
    assert "Open WebUI MemPalace checkpoint" in call["content"]
    assert "USER:" in call["content"]
    assert "ASSISTANT:" in call["content"]


def test_outlet_does_not_checkpoint_when_interval_not_met(fake_mempalace, sample_messages):
    filt = Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 3
    body = {"chat_id": "chat-1", "messages": list(sample_messages)}

    result = run(filt.outlet(body))

    assert result is body
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_default_filter_valves_match_safety_design():
    filt = Filter()

    assert filt.valves.enable_recall is True
    assert filt.valves.enable_harvest is False
    assert filt.valves.recall_limit == 5
    assert filt.valves.harvest_room == "checkpoints"


def test_inlet_appends_to_existing_system_message(fake_mempalace):
    filt = Filter()
    body = {
        "messages": [
            {"role": "system", "content": "Existing system prompt."},
            {"role": "user", "content": "Need MP recall"},
        ]
    }

    result = run(filt.inlet(body))

    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "system"
    assert result["messages"][0]["content"].startswith("Existing system prompt.")
    assert "Relevant MemPalace memories" in result["messages"][0]["content"]


def test_inlet_extracts_text_from_list_content_and_passes_wing_room(fake_mempalace):
    filt = Filter()
    filt.valves.recall_wing = "open_webui"
    filt.valves.recall_room = "integration"
    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": "list content query"}]}]}

    run(filt.inlet(body))

    call = fake_mempalace.by_name("tool_search")[0]
    assert call["query"] == "list content query"
    assert call["wing"] == "open_webui"
    assert call["room"] == "integration"


def test_inlet_ignores_invalid_messages_and_empty_user_content(fake_mempalace):
    filt = Filter()

    assert run(filt.inlet({"messages": "not-list"})) == {"messages": "not-list"}
    assert run(filt.inlet({"messages": [{"role": "user", "content": "   "}]})) == {
        "messages": [{"role": "user", "content": "   "}]
    }
    assert fake_mempalace.by_name("tool_search") == []


def test_inlet_truncates_query_to_250_chars(fake_mempalace):
    filt = Filter()
    long_text = "x" * 500

    run(filt.inlet({"messages": [{"role": "user", "content": long_text}]}))

    call = fake_mempalace.by_name("tool_search")[0]
    assert len(call["query"]) == 250
    assert call["query"] == "x" * 250


def test_inlet_recall_block_respects_max_chars(monkeypatch):
    import sys
    import types

    package = types.ModuleType("mempalace")
    server = types.ModuleType("mempalace.mcp_server")
    server.tool_search = lambda **kwargs: {"text": "Y" * 5000}
    package.mcp_server = server
    monkeypatch.setitem(sys.modules, "mempalace", package)
    monkeypatch.setitem(sys.modules, "mempalace.mcp_server", server)

    filt = Filter()
    filt.valves.recall_max_chars = 600
    result = run(filt.inlet({"messages": [{"role": "user", "content": "query"}]}))

    content = result["messages"][0]["content"]
    assert len(content) <= 600
    assert content.startswith("Relevant MemPalace memories retrieved automatically.")
    assert "Treat these as fallible recalled context" in content
    assert "Y" in content


def test_inlet_empty_recall_wing_and_room_pass_none(fake_mempalace):
    filt = Filter()
    filt.valves.recall_wing = ""
    filt.valves.recall_room = ""

    run(filt.inlet({"messages": [{"role": "user", "content": "query"}]}))

    call = fake_mempalace.by_name("tool_search")[0]
    assert call["wing"] is None
    assert call["room"] is None


def test_format_search_results_supports_variants_and_ignores_errors():
    filt = Filter()

    assert filt._format_search_results({"error": "bad"}) == ""
    assert filt._format_search_results({"formatted": "already formatted"}) == "already formatted"

    text = filt._format_search_results(
        {
            "results": [
                {"document": "doc content", "metadata": {"wing": "w", "room": "r"}, "score": 0.5},
                {"text": "text content", "wing": "w2", "room": "r2"},
                {"preview": "preview content"},
            ]
        }
    )

    assert "doc content" in text
    assert "text content" in text
    assert "preview content" in text


def test_outlet_fail_open_records_error(monkeypatch, sample_messages):
    import sys
    import types

    package = types.ModuleType("mempalace")
    server = types.ModuleType("mempalace.mcp_server")

    def boom(**kwargs):
        raise RuntimeError("write failed")

    server.tool_add_drawer = boom
    package.mcp_server = server
    monkeypatch.setitem(sys.modules, "mempalace", package)
    monkeypatch.setitem(sys.modules, "mempalace.mcp_server", server)

    filt = Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 2
    body = {"chat_id": "chat-1", "messages": list(sample_messages)}

    result = run(filt.outlet(body))

    assert result is body
    assert result["metadata"]["mempalace_harvest_error"] == "write failed"


def test_outlet_does_not_checkpoint_without_assistant(fake_mempalace):
    filt = Filter()
    filt.valves.enable_harvest = True
    body = {"chat_id": "chat-1", "messages": [{"role": "user", "content": "one"}]}

    result = run(filt.outlet(body))

    assert result is body
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_outlet_hash_source_fallback_is_stable(fake_mempalace):
    filt = Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 1
    body = {
        "chat_id": "chat-1",
        "messages": [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
        ],
    }

    run(filt.outlet(body))
    first = fake_mempalace.by_name("tool_add_drawer")[0]["source_file"]
    fake_mempalace.calls.clear()
    run(filt.outlet(body))
    second = fake_mempalace.by_name("tool_add_drawer")[0]["source_file"]

    expected_hash = filt._hash_messages(body["messages"])

    assert first == second
    assert first == f"open-webui://chat/chat-1/checkpoint/{expected_hash}"
    assert len(expected_hash) == 16
    assert all(char in "0123456789abcdef" for char in expected_hash)


def test_outlet_emits_status_event(fake_mempalace, sample_messages, event_emitter):
    filt = Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 2
    body = {"chat_id": "chat-1", "messages": list(sample_messages)}

    run(filt.outlet(body, __event_emitter__=event_emitter))

    assert event_emitter.events
    assert event_emitter.events[0]["type"] == "status"
    assert event_emitter.events[0]["data"]["done"] is True


def test_checkpoint_content_respects_harvest_max_chars(sample_messages):
    filt = Filter()
    filt.valves.harvest_max_chars = 1000
    huge_messages = list(sample_messages) + [
        {"role": "user", "content": "U" * 5000},
        {"role": "assistant", "content": "A" * 5000},
    ]

    content = filt._checkpoint_content("chat-1", 3, huge_messages)

    assert len(content) == 1000



def test_outlet_disabled_does_not_mutate_messages(fake_mempalace, sample_messages):
    from copy import deepcopy

    filt = Filter()
    body = {"chat_id": "chat-1", "messages": deepcopy(sample_messages)}
    before = deepcopy(body["messages"])

    run(filt.outlet(body))

    assert body["messages"] == before


def test_outlet_success_does_not_mutate_messages(fake_mempalace, sample_messages):
    from copy import deepcopy

    filt = Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 2
    body = {"chat_id": "chat-1", "messages": deepcopy(sample_messages)}
    before = deepcopy(body["messages"])

    run(filt.outlet(body))

    assert body["messages"] == before


def test_outlet_failure_does_not_mutate_messages(monkeypatch, sample_messages):
    from copy import deepcopy
    import sys
    import types

    package = types.ModuleType("mempalace")
    server = types.ModuleType("mempalace.mcp_server")
    server.tool_add_drawer = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("write failed"))
    package.mcp_server = server
    monkeypatch.setitem(sys.modules, "mempalace", package)
    monkeypatch.setitem(sys.modules, "mempalace.mcp_server", server)

    filt = Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 2
    body = {"chat_id": "chat-1", "messages": deepcopy(sample_messages)}
    before = deepcopy(body["messages"])

    run(filt.outlet(body))

    assert body["messages"] == before


def test_inlet_mutation_is_bounded_to_system_insertion(fake_mempalace, sample_messages):
    from copy import deepcopy

    filt = Filter()
    body = {"messages": deepcopy(sample_messages)}
    before = deepcopy(body["messages"])

    run(filt.inlet(body))

    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1:] == before


def test_filter_missing_mempalace_import_fails_open(monkeypatch, sample_messages):
    import builtins

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name.startswith("mempalace"):
            raise ModuleNotFoundError("blocked mempalace")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    filt = Filter()

    inlet_body = {"messages": [{"role": "user", "content": "recall"}]}
    inlet_result = run(filt.inlet(inlet_body))
    assert inlet_result["metadata"]["mempalace_recall_error"] == "blocked mempalace"

    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 2
    outlet_body = {"chat_id": "chat-1", "messages": list(sample_messages)}
    outlet_result = run(filt.outlet(outlet_body))
    assert outlet_result["metadata"]["mempalace_harvest_error"] == "blocked mempalace"


def test_outlet_source_uri_encodes_chat_and_message_ids(fake_mempalace):
    filt = Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 1
    body = {
        "chat_id": "folder/chat 1",
        "messages": [
            {"role": "user", "content": "one"},
            {"id": "assistant/1", "role": "assistant", "content": "two"},
        ],
    }

    run(filt.outlet(body))

    call = fake_mempalace.by_name("tool_add_drawer")[0]
    assert call["source_file"] == "open-webui://chat/folder%2Fchat%201/checkpoint/assistant%2F1"


def test_outlet_emitter_failure_is_best_effort(fake_mempalace, sample_messages):
    async def broken_emitter(event):
        raise RuntimeError("socket gone")

    filt = Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 2
    body = {"chat_id": "chat-1", "messages": list(sample_messages)}

    result = run(filt.outlet(body, __event_emitter__=broken_emitter))

    assert result is body
    assert fake_mempalace.by_name("tool_add_drawer")
