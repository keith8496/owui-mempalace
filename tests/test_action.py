from __future__ import annotations

import asyncio

from owui_mempalace_action import Action


def run(coro):
    return asyncio.run(coro)


def test_action_dry_run_reports_exchange_count_without_writing(fake_mempalace, sample_messages):
    action = Action()
    action.valves.dry_run = True
    body = {"chat_id": "chat-1", "messages": sample_messages}

    result = run(action.action(body, __user__={"id": "user-1"}))

    assert result == {
        "success": True,
        "dry_run": True,
        "chat_id": "chat-1",
        "exchanges_found": 2,
        "would_write": 2,
    }
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_action_pairs_exchanges_and_writes_stable_source_uris(fake_mempalace, sample_messages):
    action = Action()
    body = {"chat_id": "chat-1", "messages": sample_messages}

    result = run(action.action(body, __user__={"id": "user-1"}))

    assert result == {"success": True, "chat_id": "chat-1", "imported": 2, "skipped": 0, "errors": []}
    calls = fake_mempalace.by_name("tool_add_drawer")
    assert len(calls) == 2
    assert calls[0]["source_file"] == "open-webui://chat/chat-1/exchange/u1-a1"
    assert calls[1]["source_file"] == "open-webui://chat/chat-1/exchange/u2-a2"
    assert calls[0]["wing"] == "open_webui"
    assert calls[0]["room"] == "conversations"
    assert calls[0]["added_by"] == "open-webui-action:user-1"
    assert "USER:\nHow should OWUI integrate with MemPalace?" in calls[0]["content"]
    assert "ASSISTANT:\nUse Python handlers directly." in calls[0]["content"]


def test_action_uses_metadata_chat_id_when_body_lacks_chat_id(fake_mempalace, sample_messages):
    action = Action()
    body = {"messages": sample_messages[:2]}

    result = run(action.action(body, __metadata__={"chat_id": "meta-chat"}))

    assert result["chat_id"] == "meta-chat"
    call = fake_mempalace.by_name("tool_add_drawer")[0]
    assert call["source_file"] == "open-webui://chat/meta-chat/exchange/u1-a1"


def test_action_reports_already_existing_drawers_as_skipped(monkeypatch, sample_messages):
    import sys
    import types

    package = types.ModuleType("mempalace")
    server = types.ModuleType("mempalace.mcp_server")

    def add_drawer(**kwargs):
        return {"success": True, "reason": "already_exists", **kwargs}

    server.tool_add_drawer = add_drawer
    package.mcp_server = server
    monkeypatch.setitem(sys.modules, "mempalace", package)
    monkeypatch.setitem(sys.modules, "mempalace.mcp_server", server)

    action = Action()
    result = run(action.action({"chat_id": "chat-1", "messages": sample_messages}))

    assert result["success"] is True
    assert result["imported"] == 0
    assert result["skipped"] == 2
    assert result["errors"] == []


def test_action_returns_error_when_no_exchanges_found(fake_mempalace):
    action = Action()

    result = run(action.action({"chat_id": "chat-1", "messages": [{"role": "user", "content": "no answer"}]}))

    assert result == {"success": False, "error": "No user/assistant exchanges found"}
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_pair_exchanges_ignores_leading_assistant():
    action = Action()
    messages = [
        {"id": "a0", "role": "assistant", "content": "unpaired answer"},
        {"id": "u1", "role": "user", "content": "question"},
        {"id": "a1", "role": "assistant", "content": "answer"},
    ]

    pairs = action._pair_exchanges(messages)

    assert [(user["id"], assistant["id"]) for user, assistant in pairs] == [("u1", "a1")]


def test_pair_exchanges_consecutive_users_pair_latest_user():
    action = Action()
    messages = [
        {"id": "u1", "role": "user", "content": "stale question"},
        {"id": "u2", "role": "user", "content": "current question"},
        {"id": "a1", "role": "assistant", "content": "answer"},
    ]

    pairs = action._pair_exchanges(messages)

    assert [(user["id"], assistant["id"]) for user, assistant in pairs] == [("u2", "a1")]


def test_pair_exchanges_ignores_non_dict_messages():
    action = Action()
    messages = [
        "not a message",
        {"id": "u1", "role": "user", "content": "question"},
        ["also", "not", "a", "message"],
        {"id": "a1", "role": "assistant", "content": "answer"},
    ]

    pairs = action._pair_exchanges(messages)

    assert [(user["id"], assistant["id"]) for user, assistant in pairs] == [("u1", "a1")]


def test_pair_exchanges_ignores_trailing_user():
    action = Action()
    messages = [
        {"id": "u1", "role": "user", "content": "question"},
        {"id": "a1", "role": "assistant", "content": "answer"},
        {"id": "u2", "role": "user", "content": "unanswered follow-up"},
    ]

    pairs = action._pair_exchanges(messages)

    assert [(user["id"], assistant["id"]) for user, assistant in pairs] == [("u1", "a1")]


def test_default_action_valves_match_design():
    action = Action()

    assert action.valves.default_wing == "open_webui"
    assert action.valves.default_room == "conversations"
    assert action.valves.dry_run is False
    assert action.valves.max_exchanges == 100


def test_action_rejects_invalid_message_shape(fake_mempalace):
    action = Action()

    result = run(action.action({"chat_id": "chat-1", "messages": "not-list"}))

    assert result == {"success": False, "error": "No message list provided to action"}
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_action_body_id_and_unknown_chat_fallbacks(fake_mempalace, sample_messages):
    action = Action()

    by_body_id = run(action.action({"id": "body-chat", "messages": sample_messages[:2]}))
    no_id = run(action.action({"messages": sample_messages[:2]}))

    calls = fake_mempalace.by_name("tool_add_drawer")
    assert by_body_id["chat_id"] == "body-chat"
    assert no_id["chat_id"] == "unknown"
    assert calls[0]["source_file"] == "open-webui://chat/body-chat/exchange/u1-a1"
    assert calls[1]["source_file"] == "open-webui://chat/unknown/exchange/u1-a1"


def test_action_extracts_text_from_list_content(fake_mempalace):
    action = Action()
    messages = [
        {"id": "u1", "role": "user", "content": [{"type": "text", "text": "hello from list"}]},
        {"id": "a1", "role": "assistant", "content": [{"type": "text", "text": "answer from list"}]},
    ]

    run(action.action({"chat_id": "chat-1", "messages": messages}))

    content = fake_mempalace.by_name("tool_add_drawer")[0]["content"]
    assert "USER:\nhello from list" in content
    assert "ASSISTANT:\nanswer from list" in content


def test_action_respects_max_exchanges(fake_mempalace, sample_messages):
    action = Action()
    action.valves.max_exchanges = 1

    result = run(action.action({"chat_id": "chat-1", "messages": sample_messages}))

    assert result["imported"] == 1
    assert len(fake_mempalace.by_name("tool_add_drawer")) == 1


def test_action_respects_max_exchange_chars(fake_mempalace):
    action = Action()
    action.valves.max_exchange_chars = 1000
    messages = [
        {"id": "u1", "role": "user", "content": "U" * 2000},
        {"id": "a1", "role": "assistant", "content": "A" * 2000},
    ]

    run(action.action({"chat_id": "chat-1", "messages": messages}))

    assert len(fake_mempalace.by_name("tool_add_drawer")[0]["content"]) == 1000


def test_action_aggregates_returned_write_errors(monkeypatch, sample_messages):
    import sys
    import types

    package = types.ModuleType("mempalace")
    server = types.ModuleType("mempalace.mcp_server")
    calls = {"n": 0}

    def add_drawer(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            return {"success": False, "error": "second failed"}
        return {"success": True, **kwargs}

    server.tool_add_drawer = add_drawer
    package.mcp_server = server
    monkeypatch.setitem(sys.modules, "mempalace", package)
    monkeypatch.setitem(sys.modules, "mempalace.mcp_server", server)

    action = Action()
    result = run(action.action({"chat_id": "chat-1", "messages": sample_messages}))

    assert result["success"] is False
    assert result["imported"] == 1
    assert result["skipped"] == 0
    assert result["errors"] == ["second failed"]


def test_action_aggregates_exceptions_and_continues(monkeypatch, sample_messages):
    import sys
    import types

    package = types.ModuleType("mempalace")
    server = types.ModuleType("mempalace.mcp_server")
    calls = {"n": 0}

    def add_drawer(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("first exploded")
        return {"success": True, **kwargs}

    server.tool_add_drawer = add_drawer
    package.mcp_server = server
    monkeypatch.setitem(sys.modules, "mempalace", package)
    monkeypatch.setitem(sys.modules, "mempalace.mcp_server", server)

    action = Action()
    result = run(action.action({"chat_id": "chat-1", "messages": sample_messages}))

    assert result["success"] is False
    assert result["imported"] == 1
    assert result["errors"] == ["first exploded"]


def test_action_reports_import_failure(monkeypatch, sample_messages):
    import sys

    monkeypatch.delitem(sys.modules, "mempalace", raising=False)
    monkeypatch.delitem(sys.modules, "mempalace.mcp_server", raising=False)

    action = Action()
    result = run(action.action({"chat_id": "chat-1", "messages": sample_messages[:2]}))

    assert result["success"] is False
    assert result["error"].startswith("Failed to import MemPalace:")


def test_action_emits_start_and_finish_events(fake_mempalace, sample_messages, event_emitter):
    action = Action()

    run(action.action({"chat_id": "chat-1", "messages": sample_messages}, __event_emitter__=event_emitter))

    assert len(event_emitter.events) == 2
    assert event_emitter.events[0]["data"]["done"] is False
    assert event_emitter.events[1]["data"]["done"] is True


def test_action_hash_fallback_for_missing_message_ids_is_stable(fake_mempalace):
    action = Action()
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]

    run(action.action({"chat_id": "chat-1", "messages": messages}))
    first = fake_mempalace.by_name("tool_add_drawer")[0]["source_file"]
    fake_mempalace.calls.clear()
    run(action.action({"chat_id": "chat-1", "messages": messages}))
    second = fake_mempalace.by_name("tool_add_drawer")[0]["source_file"]

    assert first == second
    assert first.startswith("open-webui://chat/chat-1/exchange/")



def test_action_does_not_mutate_body_or_messages(fake_mempalace, sample_messages):
    from copy import deepcopy

    action = Action()
    body = {"chat_id": "chat-1", "messages": deepcopy(sample_messages)}
    before = deepcopy(body)

    run(action.action(body))

    assert body == before


def test_action_import_failure_uses_blocked_import(monkeypatch, sample_messages):
    import builtins

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name.startswith("mempalace"):
            raise ModuleNotFoundError("blocked mempalace")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    action = Action()

    result = run(action.action({"chat_id": "chat-1", "messages": sample_messages[:2]}))

    assert result == {"success": False, "error": "Failed to import MemPalace: blocked mempalace"}


def test_action_dry_run_emits_completed_preview_event(fake_mempalace, sample_messages, event_emitter):
    action = Action()
    action.valves.dry_run = True

    result = run(action.action({"chat_id": "chat-1", "messages": sample_messages}, __event_emitter__=event_emitter))

    assert result["dry_run"] is True
    assert len(event_emitter.events) == 2
    assert event_emitter.events[0]["data"]["done"] is False
    assert event_emitter.events[1]["data"] == {
        "description": "MemPalace dry run: would write 2 exchanges",
        "done": True,
    }
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_action_emitter_failure_is_best_effort(fake_mempalace, sample_messages):
    async def broken_emitter(event):
        raise RuntimeError("socket gone")

    action = Action()
    result = run(action.action({"chat_id": "chat-1", "messages": sample_messages}, __event_emitter__=broken_emitter))

    assert result["success"] is True
    assert result["imported"] == 2


def test_action_source_uri_encodes_chat_and_message_ids(fake_mempalace):
    action = Action()
    messages = [
        {"id": "user/1", "role": "user", "content": "hello"},
        {"id": "assistant/1", "role": "assistant", "content": "world"},
    ]

    result = run(action.action({"chat_id": "folder/chat 1", "messages": messages}))

    assert result["chat_id"] == "folder/chat 1"
    call = fake_mempalace.by_name("tool_add_drawer")[0]
    assert call["source_file"] == "open-webui://chat/folder%2Fchat%201/exchange/user%2F1-assistant%2F1"
