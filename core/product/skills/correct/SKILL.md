---
name: correct
description: Use when the owner says something in the vault is wrong or out of date, or starts a message with the word fix. Applies the correction with wd fix, which records it as the owner's.
---

# Correct

1. Put the correction in the owner's words, with full names. A made-up example: `wd fix "Sam Rivera is COO of Acme"`.
2. Run it with `--dry-run` and read what it would change. If that is what the owner meant, run it with `--apply`.
3. Tell the owner what changed, in a line or two.

The command writes the history line and records the correction as the owner's. Never edit `## History` by hand. Never edit a source. A correction that would merge two people or two companies waits until the owner says so in plain words.

If `wd fix` answers that it is not built yet, tell the owner so in one plain sentence and stop. Do not make the change by hand. A hand edit leaves no history line.
