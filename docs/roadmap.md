# Roadmap: concurrency and storage

This document records the current concurrency findings and the two planned hardening paths for the Open WebUI MemPalace integration.

The integration should remain storage-agnostic: Open WebUI plugin code calls MemPalace Python handlers, and MemPalace owns persistence. Storage backend changes belong upstream in MemPalace or in a MemPalace backend package.

## Current deployment assumptions

The near-term target is a small family Open WebUI deployment, not a large hosted service.

Known workload shape:

- up to three human users at once;
- one power user may keep multiple chats active;
- Open WebUI may run multiple backend worker processes;
- Redis is already part of the Open WebUI deployment;
- MemPalace is imported directly by Open WebUI plugin code;
- current released MemPalace storage is Chroma-backed, with Chroma's `chroma.sqlite3` and local HNSW segment files under the palace path.

The important concurrency boundary is write concurrency. Recall/search-only traffic is lower risk than concurrent writes from harvesting, add-memory tools, diary writes, KG writes, repair, or mining.

## Findings from MemPalace upstream review

Base MemPalace has added meaningful mitigations for Chroma/SQLite/HNSW failure modes:

- Chroma write methods are wrapped in a per-palace file lock via `mine_palace_lock(...)`.
- The lock is cross-process on normal local filesystems and is intended to serialize `mine`, MCP/direct writes, and backend mutators touching the same palace.
- Chroma startup has HNSW preflight/quarantine logic for stale, invalid, or structurally suspicious segment files.
- MCP/backend client caches include inode/mtime invalidation paths to recover from palace replacement or out-of-band writes.
- Knowledge graph SQLite has local locking/WAL protections, with additional upstream PRs proposing stronger multi-process retry behavior.

These mitigations lower the risk for a small household deployment, but they do not make embedded Chroma equivalent to a server database. Multiple Open WebUI worker processes can still hold independent Python module globals, MemPalace caches, Chroma clients, and KG handles.

## Risk by usage mode

Approximate risk for a small multi-worker Open WebUI deployment:

| Usage mode | Risk | Notes |
| --- | --- | --- |
| Recall/search only | Low to moderate | Mostly read paths; still depends on Chroma client/cache stability. |
| Occasional explicit writes | Moderate | MemPalace file lock should serialize many writes, but multiple OWUI workers still increase stale-handle/reconnect edge cases. |
| Automatic harvesting on every response | Moderate to high | Turns normal chat activity into a write stream across workers. Keep disabled until additional write serialization exists. |
| Bulk historical import | High | Should require dry-run/apply semantics and a maintenance window. Not implemented in this repo. |
| Concurrent `mempalace mine`, repair, or migration while OWUI is live | High | Avoid. Stop OWUI or disable memory writes during maintenance. |
| Multiple Open WebUI replicas sharing one palace path | Moderate to high | Requires stronger external coordination; Postgres becomes more attractive. |
| Palace path on NFS/SMB/cloud-synced storage | Moderate to high | SQLite, Chroma, and file locks are more fragile on network filesystems. |

## Near-term path: OWUI Redis write lock

Because Open WebUI already uses Redis, the near-term hardening path is an optional Redis-backed write lock in the OWUI plugin layer.

Current status:

- lock helper and plugin integration are implemented behind valves;
- unit tests cover helper behavior and lock-unavailable semantics;
- the feature remains experimental because it has not yet been validated in a real multi-worker Open WebUI deployment with live Redis and live MemPalace writes.

Purpose:

- serialize OWUI-originated MemPalace writes across gunicorn/uvicorn worker processes;
- reduce concurrent write pressure before requests reach Chroma;
- allow automatic harvesting to skip/fail fast instead of piling up blocked writes;
- preserve current MemPalace storage behavior and avoid forking MemPalace for a first mitigation.

Scope protected by the OWUI Redis lock:

- `owui_mempalace_tools.py` write tools such as add memory, diary write, KG write, update, or delete when enabled;
- `owui_mempalace_action.py` explicit current-chat harvesting;
- `owui_mempalace_filter.py` outlet harvesting when enabled.

Scope not protected:

- separate `mempalace` CLI processes;
- repair/migrate/mining jobs run outside Open WebUI;
- any other non-OWUI process that does not honor the same Redis key;
- Chroma internal concurrency once MemPalace itself starts a write.

Redis locking is therefore a complement to MemPalace's file lock, not a replacement.

### Proposed Redis lock semantics

Use a per-palace key:

```text
owui-mempalace:lock:write:<sha256(MEMPALACE_PALACE_PATH)>
```

Acquire with Redis `SET` using a random token and TTL:

```text
SET key token NX PX <ttl_ms>
```

Release only if the token still matches, using Lua compare-and-delete:

```lua
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
else
  return 0
end
```

This avoids deleting another worker's lock if the original TTL expires and the lock is reacquired.

Suggested initial defaults:

| Setting | Initial value | Rationale |
| --- | --- | --- |
| `use_redis_write_lock` | `false` by default | Keep the feature opt-in until deployment validation is complete. |
| `redis_lock_ttl_seconds` | `120` | Long enough for normal add/diary writes. |
| `redis_harvest_lock_ttl_seconds` | `300` | Chat harvest can take longer than a single add. |
| `redis_lock_wait_seconds` | `10` | Avoid hanging a chat request indefinitely. |
| explicit write failure mode | `error` | User should see a retryable failure. |
| automatic harvest failure mode | `skip` | Do not block or fail model responses for background capture. |

Implementation notes:

- Lock writes only by default; do not lock recall/search unless real read-during-write issues appear.
- Add jittered retry while waiting for the lock.
- If a write can exceed its TTL, either use a larger TTL or add heartbeat renewal. Do not add bulk import without a separate maintenance design.
- Keep automatic outlet harvesting disabled by default even after the Redis lock lands.
- Log lock acquisition failures without leaking message content.
- Use the manual acceptance checklist in `docs/testing.md` before enabling the feature in a non-disposable deployment.

## Longer-term path: Postgres/PGVector storage

Postgres/PGVector remains the preferred v2 storage direction for server-style or always-on memory capture deployments.

Goals:

- move write concurrency and transaction semantics into a database designed for multiple clients;
- avoid Chroma local HNSW segment-file failure modes;
- support cleaner backup/restore, observability, and multi-user/server deployments;
- keep OWUI plugins storage-agnostic.

Non-goal for this repository:

- implementing a separate vector store inside `owui-mempalace`;
- vendoring MemPalace storage code into Open WebUI plugin files.

The right layering remains:

```text
Open WebUI plugin
  -> mempalace.mcp_server tool handler
    -> MemPalace backend registry
      -> ChromaBackend today
      -> Postgres/PGVector backend later
```

### Upstream work to track

Relevant upstream/fork work identified during review:

| Reference | Status | Relevance |
| --- | --- | --- |
| MemPalace PR #995 | merged | Landed `BaseBackend`, `BaseCollection`, `PalaceRef`, typed results, and backend registry cleanup. Present in current local base repo. |
| MemPalace PR #1072 | open | Makes `MEMPALACE_BACKEND` actually select entry-point backends for normal palace access. Small but important. |
| MemPalace PR #665 | open | Adds an in-tree PostgreSQL backend with `pg_sorted_heap` preferred path and `pgvector` fallback. Best upstream-aligned reference for a native Postgres backend. |
| `malakhov-dmitrii/mempalace-postgres` | public external package | Implements a `mempalace.backends` entry-point package using Postgres + pgvector, psycopg3 pooling, JSONB metadata, and a shared table scoped by `(palace_id, collection_name, doc_id)`. Good packaging/server-shape reference. |
| MemPalace PR #1337 | open | Adds Postgres KG backend and HTTP Chroma backend for stateless deployments. Useful if/when KG moves off SQLite. |
| MemPalace PR #1556 | closed draft | Ruvector Postgres experiment; useful ideas around embedding resolver hoisting and dimension migration, but not the primary PGVector path. |

### Recommended Postgres direction

For this integration, prefer upstream or backend-package work over local plugin changes:

1. First make backend selection real and auditable in MemPalace.
2. Use an upstream/forked MemPalace package for early development if needed.
3. Keep OWUI plugin requirements and docs flexible enough to install from a fork or backend package.
4. Validate full write/read round-trip through MemPalace MCP handlers before enabling in Open WebUI.
5. Treat Chroma-specific repair/status operations as backend-specific, not generic OWUI plugin behavior.

For early alpha development, a fork may be necessary if upstream PRs have not landed. The OWUI plugin should still import `mempalace` normally; the Open WebUI backend environment decides whether that package comes from PyPI, an editable checkout, a Git branch, or a built wheel.

Example fork install pattern inside the Open WebUI backend environment:

```bash
pip uninstall -y mempalace
pip install "mempalace @ git+https://github.com/<owner>/mempalace.git@<branch>"
```

For Docker, prefer a custom Open WebUI image or pinned wheel over installing from Git at container startup.

## Recommended sequencing

1. Continue alpha testing with Chroma-backed MemPalace, conservative defaults, and explicit writes.
2. Keep optional Redis write locking implemented but disabled by default.
3. Use automated tests to guard lock semantics and use manual runtime validation to decide whether the feature is safe to enable in deployment.
4. Keep automatic outlet harvesting disabled by default.
5. Track and/or test upstream Postgres backend work in a forked MemPalace environment.
6. Only document Postgres as supported by this integration after full MemPalace handler round-trip is verified under Open WebUI.

## Operator guidance until both paths mature

- Use a local Docker volume for `/app/backend/data/mempalace`; avoid network filesystems for Chroma-backed storage.
- Persist the legacy `~/.mempalace/palace` path until MemPalace issue #1568 is fixed and verified for direct imports.
- Avoid running `mempalace mine`, repair, migrate, or bulk import while OWUI memory writes are enabled.
- Keep delete/update tools disabled unless actively testing on disposable data.
- Keep KG tools disabled unless the KG path behavior is verified in the deployment.
- Back up MemPalace storage before enabling new write paths.
- Treat Redis write locking as experimental until it passes the deployment acceptance checks in `docs/testing.md`.
