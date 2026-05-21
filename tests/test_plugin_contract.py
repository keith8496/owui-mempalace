from __future__ import annotations

from pathlib import Path

import owui_mempalace_action
import owui_mempalace_filter
import owui_mempalace_tools


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_FILES = [
    ROOT / "owui_mempalace_tools.py",
    ROOT / "owui_mempalace_filter.py",
    ROOT / "owui_mempalace_action.py",
]


def test_open_webui_plugin_shapes_are_present():
    assert hasattr(owui_mempalace_tools, "Tools")
    assert hasattr(owui_mempalace_filter, "Filter")
    assert hasattr(owui_mempalace_action, "Action")

    assert callable(owui_mempalace_tools.Tools().mempalace_search)
    assert callable(owui_mempalace_filter.Filter().inlet)
    assert callable(owui_mempalace_filter.Filter().outlet)
    assert callable(owui_mempalace_action.Action().action)


def test_plugins_do_not_import_mempalace_at_module_import_time():
    # This executable contract matters because Open WebUI should be able to load
    # plugin files before the backend runtime has a healthy palace/chromadb.
    for module in (owui_mempalace_tools, owui_mempalace_filter, owui_mempalace_action):
        assert "mempalace" not in module.__dict__


def test_plugins_do_not_implement_mcp_transport_code():
    # Documentation/comments may mention stdio MCP as the thing we are avoiding.
    # The executable contract is that plugins do not import or launch MCP
    # transports/processes themselves.
    forbidden_code = [
        "import subprocess",
        "from subprocess",
        "mcp.client",
        "streamablehttp_client",
        "stdio_client",
    ]
    for path in PLUGIN_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for term in forbidden_code:
            assert term not in text, f"{path.name} unexpectedly references {term}"


def test_plugins_only_use_approved_open_webui_source_uri_prefix():
    for path in PLUGIN_FILES:
        text = path.read_text(encoding="utf-8")
        if "open-webui://" in text:
            assert "open-webui://chat/" in text
            assert "open-webui://file/" not in text
            assert "open-webui://user/" not in text




def test_plugin_files_declare_open_webui_metadata_and_mempalace_requirement():
    expected_titles = {
        "owui_mempalace_tools.py": "title: MemPalace Tools",
        "owui_mempalace_filter.py": "title: MemPalace Recall and Harvest Filter",
        "owui_mempalace_action.py": "title: Save Chat to MemPalace",
    }
    for path in PLUGIN_FILES:
        text = path.read_text(encoding="utf-8")
        header = text.split('"""', 2)[1]
        assert expected_titles[path.name] in header
        assert "version: 0.1.0" in header
        assert "requirements: mempalace>=3.3.5" in header


def test_plugins_still_import_mempalace_lazily_despite_requirements_metadata():
    for path in PLUGIN_FILES:
        text = path.read_text(encoding="utf-8")
        body_after_docstring = text.split('"""', 2)[2]
        assert "requirements: mempalace" not in body_after_docstring
        assert "import mempalace" not in body_after_docstring
        assert "from mempalace import" in body_after_docstring

def test_plugins_import_in_subprocess_without_mempalace_runtime():
    import os
    import subprocess
    import sys

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    code = "import owui_mempalace_tools, owui_mempalace_filter, owui_mempalace_action"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_open_webui_context_parameters_remain_hidden_in_tool_signatures():
    import inspect

    forbidden_public_context_names = {"user", "metadata", "request", "event_emitter"}
    tools = owui_mempalace_tools.Tools()

    for name in dir(tools):
        if not name.startswith("mempalace_"):
            continue
        sig = inspect.signature(getattr(tools, name))
        for param in sig.parameters.values():
            assert param.name not in forbidden_public_context_names
            if param.name.strip("_") in forbidden_public_context_names:
                assert param.name.startswith("__") and param.name.endswith("__")


def test_public_plugin_methods_have_docstrings_and_jsonish_defaults():
    import inspect

    jsonish = (str, int, float, bool, type(None))
    objects = [owui_mempalace_tools.Tools(), owui_mempalace_filter.Filter(), owui_mempalace_action.Action()]

    for obj in objects:
        for name in dir(obj):
            if name.startswith("_"):
                continue
            member = getattr(obj, name)
            if not callable(member):
                continue
            if obj.__class__.__name__ == "Tools" and not name.startswith("mempalace_"):
                continue
            if obj.__class__.__name__ in {"Filter", "Action"} and name not in {"inlet", "outlet", "action"}:
                continue
            assert inspect.getdoc(member), f"{obj.__class__.__name__}.{name} needs a docstring"
            for param in inspect.signature(member).parameters.values():
                if param.default is inspect.Parameter.empty:
                    continue
                assert isinstance(param.default, jsonish), f"{name}.{param.name} has non-jsonish default"


def test_no_bulk_historical_import_surface_without_dry_run_contract():
    forbidden_public_names = ("bulk", "harvest_all", "mine_all", "import_all")
    for module in (owui_mempalace_tools, owui_mempalace_filter, owui_mempalace_action):
        for cls_name in ("Tools", "Filter", "Action"):
            cls = getattr(module, cls_name, None)
            if cls is None:
                continue
            public = [name for name in dir(cls()) if not name.startswith("_")]
            assert not any(any(term in name for term in forbidden_public_names) for name in public)
