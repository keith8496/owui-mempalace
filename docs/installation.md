# Installation

## 1. Install MemPalace in the Open WebUI backend environment

The Open WebUI backend Python process must be able to import `mempalace`.

For local development:

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

If not already initialized:

```bash
mempalace init /path/to/project-or-memory-root
mempalace mine /path/to/project-or-memory-root
```

The default palace path is usually:

```text
~/.mempalace/palace
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
- `enable_kg_tools = true`
- `max_search_results = 10`

### Filter

- `enable_recall = true`
- `enable_harvest = false`
- `recall_limit = 5`
- `recall_max_chars = 4000`

### Action

- `default_wing = open_webui`
- `dry_run = true` for first manual tests if supported by the UI.

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
