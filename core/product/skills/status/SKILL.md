---
name: status
description: Use when the owner asks what is running, when something last ran, whether anything is broken, or how many words a session loads. Runs wd status and reads status.md.
---

# Status

1. Run `wd status .` from the vault's root. It writes `status.md`.
2. Read `status.md`.
3. Answer from it in plain words. Lead with anything broken and its fix. If nothing is broken, say so in one line.

`status.md` is written by a program. Never edit it. If a check could not run, say "unknown". Do not say it passed.

If `wd status` answers that it is not built yet, tell the owner so in one plain sentence. You may read `status.md` if it is there, and say it may be out of date. Do not write it yourself.
