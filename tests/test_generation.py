from __future__ import annotations

from pathlib import Path

from scripts.generate_plugins import MARKER, PLUGIN_SRC, TARGETS, render_template


ROOT = Path(__file__).resolve().parents[1]
GENERATED_HEADER_PREFIX = "# ---------------------------------------------------------------------------\n# GENERATED FILE - DO NOT EDIT DIRECTLY\n"


def test_source_templates_exist_and_contain_exactly_one_marker():
    for template_name in TARGETS:
        text = (PLUGIN_SRC / template_name).read_text(encoding="utf-8")
        assert text.count(MARKER) == 1


def test_generated_plugins_are_up_to_date_with_templates():
    for template_name, output_path in TARGETS.items():
        expected = render_template(template_name)
        actual = output_path.read_text(encoding="utf-8")
        assert actual == expected, f"{output_path.name} is stale; run python scripts/generate_plugins.py"


def test_generated_plugins_have_header_and_no_marker():
    for output_path in TARGETS.values():
        text = output_path.read_text(encoding="utf-8")
        assert text.startswith(GENERATED_HEADER_PREFIX)
        assert MARKER not in text
        assert "# --- BEGIN injected from plugin_src/_shared_lock.py ---" in text
        assert "# --- END injected from plugin_src/_shared_lock.py ---" in text
