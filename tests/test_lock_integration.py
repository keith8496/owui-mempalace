from __future__ import annotations

import asyncio

import owui_mempalace_action
import owui_mempalace_filter
import owui_mempalace_tools


def run(coro):
    return asyncio.run(coro)


def test_tools_write_lock_unavailable_returns_explicit_error(fake_mempalace, monkeypatch):
    tools = owui_mempalace_tools.Tools()
    tools.valves.use_redis_write_lock = True

    monkeypatch.setattr(
        owui_mempalace_tools,
        "_owui_mp_write_lock",
        lambda **kwargs: (_ for _ in ()).throw(
            owui_mempalace_tools._OwuiMpLockUnavailable("MemPalace write lock unavailable; retry shortly")
        ),
    )

    result = tools.mempalace_add_drawer("open_webui", "integration", "locked")

    assert result == {"success": False, "error": "MemPalace write lock unavailable; retry shortly"}
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_action_write_lock_unavailable_returns_explicit_error(fake_mempalace, sample_messages, monkeypatch):
    action = owui_mempalace_action.Action()
    action.valves.use_redis_write_lock = True

    monkeypatch.setattr(
        owui_mempalace_action,
        "_owui_mp_write_lock",
        lambda **kwargs: (_ for _ in ()).throw(
            owui_mempalace_action._OwuiMpLockUnavailable("MemPalace write lock unavailable; retry shortly")
        ),
    )

    result = run(action.action({"chat_id": "chat-1", "messages": sample_messages}))

    assert result == {"success": False, "error": "MemPalace write lock unavailable; retry shortly"}
    assert fake_mempalace.by_name("tool_add_drawer") == []


def test_filter_outlet_write_lock_unavailable_skips_without_writing(fake_mempalace, sample_messages, monkeypatch):
    filt = owui_mempalace_filter.Filter()
    filt.valves.enable_harvest = True
    filt.valves.harvest_interval_user_messages = 2
    filt.valves.use_redis_write_lock = True
    body = {"chat_id": "chat-1", "messages": list(sample_messages)}

    monkeypatch.setattr(
        owui_mempalace_filter,
        "_owui_mp_write_lock",
        lambda **kwargs: (_ for _ in ()).throw(
            owui_mempalace_filter._OwuiMpLockUnavailable("MemPalace write lock unavailable; retry shortly")
        ),
    )

    result = run(filt.outlet(body))

    assert result is body
    assert result["metadata"]["mempalace_harvest_skipped"] == "write_lock_unavailable"
    assert fake_mempalace.by_name("tool_add_drawer") == []
