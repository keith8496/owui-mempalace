from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugin_src"
MARKER = "# [[[INJECT:OWUI_MEMPALACE_SHARED_LOCK]]]"
SHARED_PATH = PLUGIN_SRC / "_shared_lock.py"
TARGETS = {
    "owui_mempalace_tools.src.py": ROOT / "owui_mempalace_tools.py",
    "owui_mempalace_filter.src.py": ROOT / "owui_mempalace_filter.py",
    "owui_mempalace_action.src.py": ROOT / "owui_mempalace_action.py",
}
HEADER_TEMPLATE = """# ---------------------------------------------------------------------------
# GENERATED FILE - DO NOT EDIT DIRECTLY
# Source template: plugin_src/{template_name}
# Shared injected block: plugin_src/_shared_lock.py
# Regenerate with: python scripts/generate_plugins.py
# ---------------------------------------------------------------------------

"""
INJECTED_TEMPLATE = """# --- BEGIN injected from plugin_src/_shared_lock.py ---
{shared}# --- END injected from plugin_src/_shared_lock.py ---"""


def render_template(template_name: str) -> str:
    template_path = PLUGIN_SRC / template_name
    template = template_path.read_text(encoding="utf-8")
    occurrences = template.count(MARKER)
    if occurrences != 1:
        raise ValueError(f"{template_name} must contain marker exactly once; found {occurrences}")

    shared = SHARED_PATH.read_text(encoding="utf-8")
    injected = INJECTED_TEMPLATE.format(shared=shared)
    body = template.replace(MARKER, injected)
    return HEADER_TEMPLATE.format(template_name=template_name) + body


def generate() -> list[Path]:
    written: list[Path] = []
    for template_name, output_path in TARGETS.items():
        rendered = render_template(template_name)
        output_path.write_text(rendered, encoding="utf-8")
        written.append(output_path)
    return written


if __name__ == "__main__":
    for path in generate():
        print(path.relative_to(ROOT))
