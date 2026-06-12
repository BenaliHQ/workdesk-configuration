---
name: workon
description: Safely start, resume, inspect, and finish isolated repo work when the operator says "work on <repo>", "start working on", "pick up <task>", "parallel session", "is anyone else working on", or "hand this off / I'm done with this task".
---

# /workon

Keep simultaneous agent sessions from stepping on each other. Every task gets its own private copy of the repo, based on the shared version, and finished work is handed off for review.

## First use

On the first use in a conversation, briefly introduce the skill:

> I can keep this repo work isolated from other sessions. I will put this task in its own private copy, leave the main copy alone, and hand it off for review when it is ready.

## Modes

### `/workon <repo> <task>`

Also applies to conversational equivalents like "work on WorkDesk OS multi-session" or "pick up the transcript bug".

1. Run:

   ```bash
   config/scripts/repo-session.sh start <repo> <task>
   ```

2. Read the final `WORKTREE=<path>` line from the output.
3. Change into that path before reading or editing repo files.
4. Confirm in plain language:

   > I am in your private copy for `<task>`. The main copy is untouched.

5. Continue with the operator's actual task inside that private copy.

If the script warns about another session's unsaved or unshared work, relay the warning in plain words. Do not try to fix the other session's state.

### `/workon status`

Run:

```bash
config/scripts/repo-session.sh status
```

Relay the table conversationally. Say "private copy" for each workspace and "in use by another session" for held resources.

### `/workon done`

Also applies when the operator says they are finished, asks to hand this off, or asks to wrap the task.

1. Check whether there are uncommitted changes.
2. If there are changes, review them, run the relevant tests, and commit with a concise, sensible message.
3. Run:

   ```bash
   config/scripts/repo-session.sh finish <task>
   ```

4. Tell the operator the work was handed off for review. If the script prints a review URL, include it.

## Operator voice

Use zero Git vocabulary with the operator:

| Technical term | Say this instead |
|---|---|
| worktree | private copy |
| branch | do not mention it |
| pull request / PR | hand-off for review / review request |
| lock | in use by another session |
| remote / origin | shared version |

## What NOT to do

- Never work directly in `~/code/<repo>` when a multi-session scenario is possible. Always run `config/scripts/repo-session.sh start` first.
- Never commit to `main` or `master` in any shared repo. The main copy only moves when finished work is reviewed and merged.
- Never base work on the shared checkout's local state. The script guarantees work starts from the shared version; do not bypass it.
- If the script warns about another session's unshared work, relay the warning in plain words and leave that session alone.
- Do not copy files from the main checkout to "pick up" someone else's local progress unless the operator explicitly asks for that exact recovery.

## Source

- `config/scripts/repo-session.sh` owns the engine behavior.
- `config/rules/multi-session-repos.md` owns the rule.
- Incidents from 2026-06-10: one review carried another session's local work, and concurrent release checks corrupted the canary workspace.
