---
name: track
description: Use when the owner wants a word or phrase tracked, followed or linked wherever it appears. Creates the term with wd track, which gives it its own note and links every mention.
---

# Track

1. Take the phrase exactly as the owner gave it, with their spelling and capitals.
2. Run `wd track "<phrase>" --dry-run` and read what it would create and link. If it refuses because the phrase is already tracked, tell the owner and stop.
3. Run it with `--apply`.
4. Tell the owner what the command reports: the term's note and the mentions it linked.

Do not write the note under `objects/terms/` yourself, and do not add link brackets by hand. The command does both, the same way every time.

If `wd track` answers that it is not built yet, tell the owner so in one plain sentence and stop.
