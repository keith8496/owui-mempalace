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

For experiments that require an unreleased MemPalace backend, install a fork or branch into the same Open WebUI backend environment instead of relying on PyPI:

```bash
pip uninstall -y mempalace
pip install "mempalace @ git+https://github.com/<owner>/mempalace.git@<branch>"
```

Keep this repository's plugin files storage-agnostic; backend selection should be handled by MemPalace environment/config. See [roadmap.md](roadmap.md) for the Redis write-lock and Postgres/PGVector paths.

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

## 3. Development source vs deployable plugin files

The repository now keeps editable source templates under `plugin_src/` and generates the deployable root plugin files from them.

Editable sources:

- `plugin_src/owui_mempalace_tools.src.py`
- `plugin_src/owui_mempalace_filter.src.py`
- `plugin_src/owui_mempalace_action.src.py`
- `plugin_src/_shared_lock.py`

Regenerate the uploadable plugin files with:

```bash
python scripts/generate_plugins.py
```

The generated root files remain the actual Open WebUI upload artifacts:

- `owui_mempalace_tools.py`
- `owui_mempalace_filter.py`
- `owui_mempalace_action.py`

## 4. Install the Open WebUI plugins

Use Open WebUI's admin/plugin UI to load:

- `owui_mempalace_tools.py` as a Tool;
- `owui_mempalace_filter.py` as a Filter function;
- `owui_mempalace_action.py` as an Action function.

Exact upload steps may vary by Open WebUI version.

## 5. Configure valves

Recommended initial settings:

### Tools

- `enable_write_tools = true`
- `enable_delete_tools = false`
- `enable_kg_tools = false` until [MemPalace issue #1568](https://github.com/MemPalace/mempalace/issues/1568) is fixed
- `palace_path = /app/backend/data/mempalace`
- `max_search_results = 10`
- `use_redis_write_lock = false` until Redis connectivity is verified and the manual runtime checks in `docs/testing.md` pass for your deployment
- `redis_lock_ttl_seconds = 120`
- `redis_lock_wait_seconds = 10`

### Filter

- `enable_recall = true`
- `enable_harvest = false`
- `recall_limit = 5`
- `recall_max_chars = 4000`
- `palace_path = /app/backend/data/mempalace`
- `use_redis_write_lock = false` until Redis connectivity is verified and the manual runtime checks in `docs/testing.md` pass for your deployment
- `redis_harvest_lock_ttl_seconds = 300`
- `redis_lock_wait_seconds = 2`

### Action

- `default_wing = open_webui`
- `dry_run = true` for first manual tests if supported by the UI.
- `palace_path = /app/backend/data/mempalace`
- `use_redis_write_lock = false` until Redis connectivity is verified and the manual runtime checks in `docs/testing.md` pass for your deployment
- `redis_harvest_lock_ttl_seconds = 300`
- `redis_lock_wait_seconds = 10`

Redis-backed write locking uses the same backend environment Redis settings that Open WebUI typically uses, including `REDIS_URL` and `REDIS_KEY_PREFIX`, with optional Sentinel/cluster environment variables when present.

Treat Redis write locking as experimental until it has been manually validated in the same Open WebUI worker/replica topology you plan to run.

## 6. Basic verification

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
