# Chat harvesting strategy

## Goals

Harvesting should preserve useful Open WebUI conversation context in MemPalace without surprising the user or corrupting the palace with duplicates.

## Modes

### Explicit add-drawer tool

The model or user explicitly calls `mempalace_add_drawer` with a wing, room, and content.

This is the safest storage path.

### Current-chat action

The action plugin can harvest the current chat. It should:

1. read the current chat body passed by Open WebUI;
2. pair user and assistant messages into exchanges;
3. write each exchange to MemPalace using deterministic source URIs;
4. report imported/skipped counts.

### Outlet checkpoint filter

The filter can optionally checkpoint conversations after N user turns.

Default: disabled.

When enabled, it should avoid mutating chat output and should only perform best-effort checkpoint writes.

## Source URI scheme

Use stable source identifiers:

```text
open-webui://chat/<chat_id>/message/<message_id>
open-webui://chat/<chat_id>/exchange/<user_message_id>-<assistant_message_id>
open-webui://chat/<chat_id>/checkpoint/<assistant_message_id>
```

## Duplicate prevention

MemPalace `tool_add_drawer` uses deterministic drawer IDs based on wing, room, and content. The integration should also provide stable `source_file` metadata to make duplicate detection and audits easier.

Additional safeguards:

- call `tool_check_duplicate` before storing long content;
- store last harvested message IDs in a state file if automatic harvesting becomes common;
- use dry-run for bulk historical import.

## Room mapping

Initial room mapping:

| Content | Room |
| --- | --- |
| User/assistant exchange | `conversations` |
| Session checkpoint | `checkpoints` |
| Extracted decision | `decisions` |
| Extracted preference | `preferences` |
| Extracted problem | `problems` |
| Extracted milestone | `milestones` |

The first version stores exchanges/checkpoints. General extraction can be added later by using MemPalace's `general_extractor.extract_memories`.

## Bulk historical harvesting

Bulk import should be implemented later with an explicit dry-run/apply flow.

Suggested options:

- `limit`
- `updated_after`
- `include_archived`
- `mode = exchange | general`
- `wing`
- `dry_run`

Bulk harvesting should probably become an Open WebUI backend route or background job if progress tracking is needed.
