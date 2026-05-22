from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SHARED_LOCK_PATH = ROOT / "plugin_src" / "_shared_lock.py"


@pytest.fixture
def shared_lock_module():
    spec = importlib.util.spec_from_file_location("shared_lock_test_module", SHARED_LOCK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeRedisClient:
    def __init__(self, *, set_results=None):
        self.set_results = list(set_results or [True])
        self.set_calls = []
        self.eval_calls = []

    def set(self, key, token, nx=True, ex=60):
        self.set_calls.append({"key": key, "token": token, "nx": nx, "ex": ex})
        if self.set_results:
            return self.set_results.pop(0)
        return False

    def eval(self, script, numkeys, key, token):
        self.eval_calls.append({"script": script, "numkeys": numkeys, "key": key, "token": token})
        return 1


def test_write_lock_disabled_is_noop(shared_lock_module, monkeypatch):
    monkeypatch.setattr(shared_lock_module, "_owui_mp_get_redis_client", lambda: (_ for _ in ()).throw(AssertionError("should not fetch redis")))

    with shared_lock_module._owui_mp_write_lock(
        enabled=False,
        palace_path="/tmp/palace",
        ttl_seconds=60,
        wait_seconds=1,
    ):
        pass


def test_write_lock_acquires_and_releases(shared_lock_module, monkeypatch):
    client = FakeRedisClient(set_results=[True])
    monkeypatch.setattr(shared_lock_module, "_owui_mp_get_redis_client", lambda: client)

    with shared_lock_module._owui_mp_write_lock(
        enabled=True,
        palace_path="/tmp/palace",
        ttl_seconds=60,
        wait_seconds=1,
    ):
        pass

    assert len(client.set_calls) == 1
    assert client.set_calls[0]["nx"] is True
    assert client.set_calls[0]["ex"] == 60
    assert len(client.eval_calls) == 1
    assert client.eval_calls[0]["key"].startswith("open-webui:mempalace:lock:write:")
    assert client.eval_calls[0]["token"] == client.set_calls[0]["token"]


def test_write_lock_timeout_raises(shared_lock_module, monkeypatch):
    client = FakeRedisClient(set_results=[False])
    monkeypatch.setattr(shared_lock_module, "_owui_mp_get_redis_client", lambda: client)
    monkeypatch.setattr(shared_lock_module.time, "monotonic", lambda: 100.0)

    with pytest.raises(shared_lock_module._OwuiMpLockUnavailable, match="MemPalace write lock unavailable; retry shortly"):
        with shared_lock_module._owui_mp_write_lock(
            enabled=True,
            palace_path="/tmp/palace",
            ttl_seconds=60,
            wait_seconds=0,
        ):
            pass


def test_write_lock_missing_redis_raises(shared_lock_module, monkeypatch):
    monkeypatch.setattr(shared_lock_module, "_owui_mp_get_redis_client", lambda: None)

    with pytest.raises(shared_lock_module._OwuiMpLockUnavailable, match="MemPalace write lock unavailable; retry shortly"):
        with shared_lock_module._owui_mp_write_lock(
            enabled=True,
            palace_path="/tmp/palace",
            ttl_seconds=60,
            wait_seconds=1,
        ):
            pass
