# Testing checklist

This repository now has two verification layers:

1. automated pytest coverage for generated plugin artifacts, wrapper contracts, and lock behavior;
2. manual Open WebUI runtime checks against a real backend environment.

For normal development, regenerate the root plugin files first:

```bash
python scripts/generate_plugins.py
```

Then run the automated suite:

```bash
python -m pytest
```

Expected automated coverage includes:

- plugin wrapper behavior and safety valves;
- lazy MemPalace import contracts;
- generated-plugin freshness checks;
- shared Redis write-lock helper behavior;
- lock-unavailable behavior differences across tools, filter outlet, and action paths.

## Import test

Run in the Open WebUI backend Python environment:

```bash
python - <<'PY'
import mempalace
print(mempalace.__version__)
from mempalace.mcp_server import tool_status
print(tool_status())
PY
```

Expected:

- import succeeds;
- status returns a dictionary;
- no Chroma dependency conflict appears.

## Tool plugin tests

1. Load `owui_mempalace_tools.py`.
2. Enable it for a test model.
3. Ask the model to call `mempalace_status`.
4. Ask the model to call `mempalace_search`.
5. Ask the model to store a test memory with `mempalace_add_drawer`.
6. Search for the stored memory.
7. If testing Redis write locking, enable `use_redis_write_lock` only in a deployment where `REDIS_URL` is configured and reachable.

## Filter plugin tests

1. Load `owui_mempalace_filter.py`.
2. Enable recall.
3. Disable harvesting.
4. Store a unique memory.
5. Start a fresh chat with a related prompt.
6. Confirm the model uses the recalled memory.
7. Confirm the prompt is not flooded; recall block should respect `recall_max_chars`.
8. If testing outlet write locking, enable `use_redis_write_lock` and confirm lock contention skips checkpoint writes without breaking chat responses.

## Action plugin tests

1. Load `owui_mempalace_action.py`.
2. Create a short disposable chat.
3. Run the action.
4. Confirm the action reports imported/skipped counts.
5. Re-run the action and confirm duplicates are skipped or idempotent.
6. Search MemPalace for content from the chat.
7. If testing Redis write locking, enable `use_redis_write_lock` and confirm lock contention returns a clear retryable error.

## Safety tests

- Set `enable_write_tools = false` and confirm writes are rejected.
- Keep `enable_delete_tools = false` and confirm delete is rejected.
- Disable recall and confirm no memory block is injected.
- Enable outlet harvesting only in a disposable chat first.
- Keep Redis write locking disabled by default until Redis connectivity is validated in the same Open WebUI backend environment.

## Failure modes to observe

- MemPalace not installed in OWUI backend environment.
- Chroma import/version conflict.
- Palace not initialized.
- Long first search due to Chroma cold start.
- Duplicate writes after retry/reload.
- Redis configured in deployment but unreachable from the Open WebUI backend process.
- Lock contention causing explicit writes to fail clearly or automatic checkpoint harvesting to skip safely.
