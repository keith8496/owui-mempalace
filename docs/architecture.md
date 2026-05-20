# Architecture

## Problem

MemPalace provides a Python package and a stdio MCP server. Open WebUI currently supports Python tools/functions and HTTP-style MCP tool servers, but not stdio MCP servers directly. The goal is to make MemPalace useful inside Open WebUI without first adding stdio MCP transport support.

## Approach

Use MemPalace's Python API directly from Open WebUI plugin files.

The richest stable integration surface in MemPalace today is `mempalace.mcp_server`, which defines plain Python handler functions such as:

- `tool_search`
- `tool_add_drawer`
- `tool_status`
- `tool_diary_write`
- `tool_kg_query`
- `tool_list_drawers`

The Open WebUI plugin layer wraps these functions and exposes them as:

- model-callable tools,
- inlet/outlet filters,
- user-triggered actions.

## Components

### Tool plugin

`owui_mempalace_tools.py`

Responsibilities:

- expose explicit MemPalace operations to the model;
- keep destructive operations disabled by default;
- attach Open WebUI provenance via `source_file` and `added_by` metadata;
- use hidden Open WebUI context params such as `__user__` and `__metadata__` when available.

### Filter plugin

`owui_mempalace_filter.py`

Responsibilities:

- inlet: search MemPalace using the latest user message and inject compact recalled context;
- outlet: optionally checkpoint completed conversations to MemPalace;
- avoid mutating assistant output unless explicitly designed later.

### Action plugin

`owui_mempalace_action.py`

Responsibilities:

- let users explicitly harvest the current chat;
- emit progress/status events where Open WebUI provides an event emitter;
- provide a safer path for bulk/historical import than automatic outlet behavior.

## Data flow

### Explicit tool call

```text
Model requests mempalace_search
  -> Open WebUI tool plugin
  -> mempalace.mcp_server.tool_search
  -> MemPalace palace
  -> tool result returned to model
```

### Automatic recall

```text
Incoming chat body
  -> filter inlet
  -> last user message extracted
  -> MemPalace search
  -> compact recall block inserted as system context
  -> model generation
```

### Conservative harvesting

```text
Completed chat body
  -> filter outlet or action
  -> active branch messages paired as user/assistant exchanges
  -> deterministic source URI assigned
  -> MemPalace add_drawer
```

## Provenance scheme

Open WebUI-originated content should use stable source URIs:

```text
open-webui://chat/<chat_id>/message/<message_id>
open-webui://chat/<chat_id>/exchange/<user_message_id>-<assistant_message_id>
open-webui://chat/<chat_id>/checkpoint/<assistant_message_id>
```

This gives MemPalace deterministic source metadata and makes duplicate prevention easier.

## Deployment modes

### Single-user local

Use the default palace path:

```text
~/.mempalace/palace
```

This is the simplest and is the assumed first target.

### Multi-user Open WebUI

Multi-user deployments need stricter isolation. Options:

1. one shared palace with user-specific wings;
2. per-user palace paths;
3. a separate MemPalace bridge service that isolates process/global state per user.

The first plugin version does not guarantee multi-user isolation beyond metadata tagging.

## Why not stdio MCP first?

Adding stdio MCP support to Open WebUI would be useful generally, but it is not necessary for MemPalace feature parity. MemPalace's MCP tools are implemented as Python handler functions, so direct wrapping is less code, easier to debug, and avoids transport/process lifecycle issues.
