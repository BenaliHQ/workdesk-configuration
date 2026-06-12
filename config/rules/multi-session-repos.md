# Multi-Session Repos

Multiple agents may work on the same repo at the same time. The default is isolation: one session gets one private workspace, starts from the shared remote state, and hands off finished work for review. Shared mutable checkout state is never a coordination mechanism.

## When this applies

This applies whenever Claude, Codex, or another agent is working in a repo that another session could also touch, especially repos under `~/code/` and release workflows that use a shared staging resource.

It also applies when the operator asks who is working on something, starts a parallel session, resumes a task, or finishes a task for review.

## What to do

**Isolate working state.** One session equals one private workspace, created by:

```bash
config/scripts/repo-session.sh start <repo> <task>
```

Never put two live sessions in the same checkout.

**Coordinate only via origin.** Sessions communicate through push, review, and merge. Do not communicate by reading or copying a shared local checkout. New task work always starts from `origin/<default>`.

**Keep `main` merge-only.** Do not make local commits to the default branch of a shared repo. The default branch moves only by merging reviewed hand-offs.

**Serialize exclusive resources.** If a resource cannot be isolated, protect it with:

```bash
config/scripts/repo-session.sh lock <name> -- <command...>
```

For multi-step phases, use `lock-acquire <name>` and `lock-release <name>` around the exclusive section.

**Attribute work in names.** Claude work uses `claude/<task>`. Codex work uses `codex/<task>`.

**Use the same engine for both agents.** Claude reaches this through `/workon`. Codex follows AGENTS.md and calls `config/scripts/repo-session.sh` directly.

## What NOT to do

- Do not start work in `~/code/<repo>` when another session could be involved.
- Do not base work on an unpushed local checkout, even if it looks cleaner or more recent.
- Do not commit directly to `main` or `master` in a shared repo.
- Do not copy files between local checkouts to coordinate sessions.
- Do not run two release canary smokes against `~/.workdesk-canary` at the same time; use the repo-session lock.
- Do not delete another session's private workspace or release a lock unless the holder is dead or the operator explicitly asks for cleanup.

## Source

- Session 2026-06-10: PR #54 carried another session's `process-transcripts` work because a session branched from a local `main` that had unpushed commits.
- Session 2026-06-10: two concurrent canary smokes wrote to the same release canary at `~/.workdesk-canary`, corrupting shared staging state and causing a JSON parse failure mid-apply.
- Engine: `config/scripts/repo-session.sh`.
- Operator-facing skill: `config/skills/workon/SKILL.md`.
