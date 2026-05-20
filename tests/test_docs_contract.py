from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_documents_safety_defaults_and_components():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Avoid implementing stdio MCP transport" in text
    assert "Recall enabled by default" in text
    assert "delete tools disabled" in text
    assert "Automatic harvesting disabled by default" in text
    assert "owui_mempalace_tools.py" in text
    assert "owui_mempalace_filter.py" in text
    assert "owui_mempalace_action.py" in text


def test_architecture_documents_direct_python_wrapping_decision():
    text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

    assert "Use MemPalace's Python API directly" in text
    assert "without first adding stdio MCP transport support" in text
    assert "mempalace.mcp_server" in text
    assert "open-webui://chat/<chat_id>/exchange/<user_message_id>-<assistant_message_id>" in text


def test_harvesting_docs_define_conservative_defaults_and_source_uris():
    text = (ROOT / "docs" / "harvesting.md").read_text(encoding="utf-8")

    assert "Default: disabled" in text
    assert "avoid mutating chat output" in text
    assert "open-webui://chat/<chat_id>/checkpoint/<assistant_message_id>" in text
    assert "use dry-run for bulk historical import" in text
    assert "User/assistant exchange | `conversations`" in text
