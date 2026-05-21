# Installation

## 1. Install MemPalace in the Open WebUI backend environment

The Open WebUI backend Python process must be able to import `mempalace`.

The plugin files declare Open WebUI requirements metadata:

```text
requirements: mempalace>=3.3.5
```

Open WebUI should install MemPalace and its Python dependencies automatically when each plugin is loaded. If automatic installation fails or plugin-managed installs are disabled, install MemPalace manually in the Open WebUI backend environment:

```bash
pip install "mempalace>=3.3.5"
```

For local editable development, install from a checkout instead:

```bash
pip install -e /home/u7de088ca/projects/mempalace
```

Verify from the same environment that runs Open WebUI:

```bash
python - <<'PY'
import mempalace
print(mempalace.__version__)
from mempalace.mcp_server import tool_status
print(tool_status())
PY
```

## 2. Initialize MemPalace

For Open WebUI, use the backend persistent data directory as the palace path:

```text
/app/backend/data/mempalace
```

Set this in the Open WebUI backend environment before the first plugin call:

```bash
export MEMPALACE_PALACE_PATH=/app/backend/data/mempalace
```

The plugins also set this default before lazy-importing MemPalace when `MEMPALACE_PALACE_PATH` is unset or blank. Explicit environment configuration is preferred because it makes the storage location auditable.

Until [MemPalace issue #1568](https://github.com/MemPalace/mempalace/issues/1568) is fixed and verified in Open WebUI, Docker deployments should also persist MemPalace's legacy default palace directory so accidental/default-path writes are not lost on container restart:

```text
~/.mempalace/palace
```

If your Open WebUI image runs as `root`, this usually means persisting:

```text
/root/.mempalace/palace
```

If not already initialized, initialize and mine using the same backend environment:

```bash
mempalace --palace /app/backend/data/mempalace init /path/to/project-or-memory-root
mempalace --palace /app/backend/data/mempalace mine /path/to/project-or-memory-root
```

## 3. Install the Open WebUI plugins

Use Open WebUI's admin/plugin UI to load:

- `owui_mempalace_tools.py` as a Tool;
- `owui_mempalace_filter.py` as a Filter function;
- `owui_mempalace_action.py` as an Action function.

Exact upload steps may vary by Open WebUI version.

## 4. Configure valves

Recommended initial settings:

### Tools

- `enable_write_tools = true`
- `enable_delete_tools = false`
- `enable_kg_tools = false` until [MemPalace issue #1568](https://github.com/MemPalace/mempalace/issues/1568) is fixed
- `palace_path = /app/backend/data/mempalace`
- `max_search_results = 10`

### Filter

- `enable_recall = true`
- `enable_harvest = false`
- `recall_limit = 5`
- `recall_max_chars = 4000`
- `palace_path = /app/backend/data/mempalace`

### Action

- `default_wing = open_webui`
- `dry_run = true` for first manual tests if supported by the UI.
- `palace_path = /app/backend/data/mempalace`

## 5. Basic verification

Ask a model with the tool enabled:

```text
Use MemPalace status and tell me how many drawers exist.
```

Then test a write:

```text
Store this exact memory in MemPalace under wing open_webui room integration: OWUI can call MemPalace Python handlers directly.
```

Then verify search:

```text
Search MemPalace for OWUI Python handlers.
```
