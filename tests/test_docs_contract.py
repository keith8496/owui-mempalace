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
    assert "/app/backend/data/mempalace" in text
    assert "MEMPALACE_PALACE_PATH" in text
    assert "requirements: mempalace>=3.3.5" in text


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


def test_docs_pin_open_webui_palace_path_and_kg_limitation():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    installation = (ROOT / "docs" / "installation.md").read_text(encoding="utf-8")
    combined = "\n".join([readme, architecture, installation])

    assert "/app/backend/data/mempalace" in readme
    assert "/app/backend/data/mempalace" in architecture
    assert "/app/backend/data/mempalace" in installation
    assert "MEMPALACE_PALACE_PATH" in combined
    assert "MemPalace issue #1568" in combined
    assert "~/.mempalace/palace" in combined
    assert "Docker deployments should also persist" in combined
    assert "enable_kg_tools = false" in installation
    assert "requirements: mempalace>=3.3.5" in installation
    assert 'pip install "mempalace>=3.3.5"' in installation
