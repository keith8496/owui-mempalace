# owui-mempalace

Open WebUI plugin integration for [MemPalace](https://github.com/mempalace/mempalace).

This repository contains first-pass Open WebUI plugin files that expose MemPalace memory operations without requiring Open WebUI to support stdio MCP. The integration calls MemPalace's Python handlers directly and maps them onto Open WebUI tools, filters, and actions.

## Goals

- Provide Open WebUI feature parity with using MemPalace in Claude Code or Codex.
- Avoid implementing stdio MCP transport in Open WebUI for the first version.
- Keep the integration reviewable as small, uploadable Open WebUI plugin files.
- Support explicit memory operations, automatic recall, and conservative chat harvesting.

## Components

| File | Purpose |
| --- | --- |
| `owui_mempalace_tools.py` | Model-callable Open WebUI tools for MemPalace search, storage, status, diary, and KG operations. |
| `owui_mempalace_filter.py` | Open WebUI filter for automatic recall injection and optional post-chat checkpoint harvesting. |
| `owui_mempalace_action.py` | Open WebUI action for user-triggered current-chat harvesting. |
| `docs/architecture.md` | Design and component architecture. |
| `docs/installation.md` | Installation and setup notes. |
| `docs/harvesting.md` | Chat harvesting strategy and safety model. |
| `docs/testing.md` | Manual verification checklist. |

## Current status

This is an initial scaffold. The plugins are intentionally conservative:

- Writes are valve-gated.
- Delete/update tools are disabled by default; write tools are valve-gated.
- Automatic outlet harvesting is disabled by default.
- The first implementation assumes a single MemPalace palace path unless configured otherwise.

## Requirements

- Open WebUI with custom tools/functions enabled.
- Python environment where `mempalace` can be imported by the Open WebUI backend.
- MemPalace initialized at the configured palace path, usually:

```text
~/.mempalace/palace
```

For local development, install MemPalace into the Open WebUI backend environment:

```bash
pip install -e /home/u7de088ca/projects/mempalace
```

Then verify:

```bash
python - <<'PY'
import mempalace
print(mempalace.__version__)
from mempalace.mcp_server import tool_status
print(tool_status())
PY
```

## Design summary

MemPalace already exposes a rich Python API through `mempalace.mcp_server` handler functions. Open WebUI does not need to speak MemPalace's stdio MCP protocol to use those capabilities. This integration wraps the handlers directly.

```text
Open WebUI model/tool call
    -> OWUI plugin function
        -> mempalace.mcp_server.tool_*
            -> MemPalace Chroma-backed palace
```

Automatic recall uses an inlet filter:

```text
user message -> MemPalace search -> compact memory block -> system prompt context
```

Chat harvesting uses either:

- explicit model/user tools (`mempalace_add_drawer`, `Save chat to MemPalace`), or
- optional outlet checkpoints after a configured number of user turns.

## Safety defaults

The initial defaults are designed to avoid surprising data movement:

- Recall enabled by default.
- Write tools enabled by default, but delete tools disabled.
- Automatic harvesting disabled by default.
- Historical/bulk import not implemented in plugin v0; it should be added with dry-run first.

## Repository layout

```text
.
├── README.md
├── docs/
│   ├── architecture.md
│   ├── harvesting.md
│   ├── installation.md
│   └── testing.md
├── owui_mempalace_action.py
├── owui_mempalace_filter.py
└── owui_mempalace_tools.py
```

## Next implementation steps

1. Load `owui_mempalace_tools.py` into Open WebUI and verify status/search/add-drawer.
2. Load `owui_mempalace_filter.py` and verify recall injection.
3. Enable action plugin and test current-chat harvesting on a disposable chat.
4. Decide whether bulk harvesting belongs in an action plugin or a source-level Open WebUI backend route.

