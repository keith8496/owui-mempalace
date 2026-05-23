# owui-mempalace

Open WebUI plugin integration for [MemPalace](https://github.com/mempalace/mempalace).

This repository contains Open WebUI plugin files that expose MemPalace memory operations without requiring Open WebUI to support stdio MCP. The integration calls MemPalace's Python handlers directly and maps them onto Open WebUI tools, filters, and actions.

## Goals

- Provide Open WebUI feature parity with using MemPalace in Claude Code or Codex.
- Avoid implementing stdio MCP transport in Open WebUI for the first version.
- Keep the integration reviewable as small, uploadable Open WebUI plugin files.
- Support explicit memory operations, automatic recall, and conservative chat harvesting.

## Components

| File | Purpose |
| --- | --- |
| `owui_mempalace_tools.py` | Generated self-contained Open WebUI tools plugin for MemPalace search, storage, status, diary, and KG operations. |
| `owui_mempalace_filter.py` | Generated self-contained Open WebUI filter for automatic recall injection and optional post-chat checkpoint harvesting. |
| `owui_mempalace_action.py` | Generated self-contained Open WebUI action for user-triggered current-chat harvesting. |
| `plugin_src/` | Editable source templates and shared injected blocks used to generate deployable plugin files. |
| `scripts/generate_plugins.py` | Regenerates the self-contained plugin files from `plugin_src/`. |
| `docs/architecture.md` | Design and component architecture. |
| `docs/installation.md` | Installation and setup notes. |
| `docs/harvesting.md` | Chat harvesting strategy and safety model. |
| `docs/testing.md` | Automated/manual verification guidance. |
| `docs/roadmap.md` | Concurrency/storage roadmap, including Redis write locking and Postgres/PGVector paths. |

## Current status

This is an initial alpha scaffold. The plugins are intentionally conservative:

- Writes are valve-gated.
- Delete/update tools are disabled by default; write tools are valve-gated.
- Automatic outlet harvesting is disabled by default.
- Knowledge graph tools are disabled by default until upstream MemPalace KG storage honors `MEMPALACE_PALACE_PATH` for direct Python imports.
- The first implementation assumes a single MemPalace palace path under `/app/backend/data/mempalace` unless configured otherwise.
- Redis-backed OWUI-side write locking is scaffolded behind per-plugin valves, remains experimental, and still needs live Open WebUI multi-worker validation.

## Requirements

- Open WebUI with custom tools/functions enabled.
- Python environment where `mempalace` can be imported by the Open WebUI backend.
- MemPalace initialized at the Open WebUI persistent data path:

```text
/app/backend/data/mempalace
```

The plugins set `MEMPALACE_PALACE_PATH` to that path before lazy-importing MemPalace when the environment variable is unset or blank. Prefer setting the same value explicitly in the Open WebUI backend environment.

Until [MemPalace issue #1568](https://github.com/MemPalace/mempalace/issues/1568) is fixed and verified in Open WebUI, also persist MemPalace's legacy default palace directory in Docker so accidental/default-path writes survive container restarts:

```text
~/.mempalace/palace
```

Each plugin file declares Open WebUI metadata with:

```text
requirements: mempalace>=3.3.5
```

Open WebUI should install MemPalace and its Python dependencies automatically when the plugin is loaded. If automatic installation fails or your deployment disables plugin-managed installs, install MemPalace manually in the Open WebUI backend environment:

```bash
pip install "mempalace>=3.3.5"
```

For local editable development, install from a checkout instead:

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

The editable source of truth now lives under `plugin_src/`, while the root plugin files remain the deployable Open WebUI artifacts.

## Safety defaults

The initial defaults are designed to avoid surprising data movement:

- Recall enabled by default.
- Write tools enabled by default, but update/delete tools disabled.
- Knowledge graph tools disabled by default; see [MemPalace issue #1568](https://github.com/MemPalace/mempalace/issues/1568).
- Automatic harvesting disabled by default.
- Redis write locking disabled by default until explicitly configured and manually validated in the target deployment.
- Historical/bulk import not implemented in plugin v0; it should be added with dry-run first.

## Repository layout

```text
.
├── README.md
├── docs/
│   ├── architecture.md
│   ├── harvesting.md
│   ├── installation.md
│   ├── roadmap.md
│   └── testing.md
├── plugin_src/
│   ├── _shared_lock.py
│   ├── owui_mempalace_action.src.py
│   ├── owui_mempalace_filter.src.py
│   └── owui_mempalace_tools.src.py
├── scripts/
│   └── generate_plugins.py
├── tests/
├── owui_mempalace_action.py
├── owui_mempalace_filter.py
└── owui_mempalace_tools.py
```

## Development workflow

The root plugin files are the deployable Open WebUI artifacts, but they are generated from source templates so shared logic does not need to be hand-copied across three files.

Edit:

- `plugin_src/owui_mempalace_tools.src.py`
- `plugin_src/owui_mempalace_filter.src.py`
- `plugin_src/owui_mempalace_action.src.py`
- `plugin_src/_shared_lock.py`

Then regenerate the uploadable plugin files:

```bash
python scripts/generate_plugins.py
```

Do not hand-edit the generated root plugin files unless you are intentionally debugging the generator output. Regenerate before running tests or uploading updated plugins into Open WebUI.

## Current verification status

The repo now includes automated pytest coverage for:

- plugin wrapper behavior and safety valves;
- lazy MemPalace import contracts;
- generated-plugin freshness checks;
- shared Redis write-lock helper behavior;
- lock-unavailable behavior differences across tools, filter outlet, and action paths.

Manual Open WebUI runtime verification is still required before calling a deployment path production-ready. In particular, Redis write locking is unit-tested but not yet confirmed in a real multi-worker Open WebUI deployment. See `docs/testing.md`.

## Next implementation steps

1. Load `owui_mempalace_tools.py` into Open WebUI and verify status/search/add-drawer.
2. Load `owui_mempalace_filter.py` and verify recall injection.
3. Enable action plugin and test current-chat harvesting on a disposable chat.
4. Validate Redis-backed write locking in a live multi-worker Open WebUI deployment using the manual acceptance checklist in `docs/testing.md`.
5. Decide whether bulk harvesting belongs in an action plugin or a source-level Open WebUI backend route.
6. Track upstream MemPalace Postgres/PGVector backend work for a future storage-backend v2; see `docs/roadmap.md`.
