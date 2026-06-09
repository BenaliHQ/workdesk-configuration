# Upstream Release Discipline

Anything that should persist across `/update` runs MUST round-trip through the upstream WorkDesk OS release flow. Vault-local files in synced directories die. If a skill, rule, script, schema, prompt, or template was built directly in the vault without an upstream PR + release, it is at risk every time `/update` is invoked — even by another Claude Code session in the background.

## When this applies

- Creating any file in `.claude/skills/`, `.claude/rules/`, `.claude/objects/`, `.claude/sources/`, `.claude/practices/`, `.claude/signals/`, `.claude/templates/`, or `config/scripts/` that should persist
- Modifying any existing upstream-tracked file in those same locations
- Promoting a learning, rule, or pattern out of `learnings.md` or session-logs into a durable location
- Restoring a file that was lost to a prior `/update` revert

## The model

WorkDesk OS has two locations for the same logical artifact:

| Location | What lives here | Lifecycle |
|---|---|---|
| Upstream repo `config/skills/X/SKILL.md` | Source of truth, version-controlled, in releases | Persists across `/update` |
| Vault `.claude/skills/X/SKILL.md` | Rendered location Claude Code reads from | Overwritten by `/update` from upstream baseline |

`/update` does NOT touch operator zones (`personal/`, `atlas/`, `gtd/`, `intel/`, `system/`). Those are safe to write directly.

`/update` DOES enforce upstream's view of the configuration tree. If a file exists in the vault but not upstream, behavior in this vault's history has been inconsistent: scripts in `config/scripts/` survived multiple updates, but skill folders in `.claude/skills/` were swept. **Assume vault-local = at risk** until proven otherwise on your specific path.

## What to do

### 1. Decide where the artifact belongs

| Artifact location in vault | Where it lives upstream | Goes through `/release`? |
|---|---|---|
| `.claude/skills/*` | `config/skills/*` | Yes |
| `.claude/rules/*` | `config/rules/*` | Yes |
| `.claude/rules/writing-style.md` | (operator-owned — seeded from `config/templates/writing-style.md`, never shipped) | No — write directly |
| `.claude/objects/*` | `config/objects/*` | Yes |
| `.claude/sources/*` | `config/sources/*` | Yes |
| `.claude/practices/*` | `config/practices/*` | Yes |
| `.claude/signals/*` | `config/signals/*` | Yes |
| `.claude/templates/*` | `config/templates/*` | Yes |
| `config/scripts/*` | `config/scripts/*` | Yes |
| `personal/`, `atlas/`, `gtd/`, `intel/`, `system/` | (operator zone, not synced) | No — write directly |

If your artifact belongs in an operator zone, write directly. If it belongs anywhere else, plan for `/release` from the start.

**Operator-owned config files.** `writing-style.md` is the exception in `config/rules/`: it holds the operator's personal voice, words-to-avoid list, and formatting preferences (the Stop hook appends `[STYLE]` corrections to it). Shipping it would broadcast one operator's preferences to all operators AND risk `/update` overwriting accumulated preferences. So it is **not shipped** — `config/templates/writing-style.md` is the generic seed, `/onboarding` materializes it once if absent, and the `/update` engine then classifies the operator's copy as `operator-only` (preserved silently). Never re-add `writing-style.md` to the shipped `config/rules/` tree. If another config file turns out to be operator-personal in the same way, give it the same treatment: generic template in `config/templates/`, seeded by onboarding, absent from the shipped rules.

### 2. Write vault-local first for immediate effect, then release upstream

Two-step pattern that works for both immediate iteration AND durability:

1. **Iterate in vault.** Create the file in `.claude/skills/X/`, `.claude/rules/X.md`, etc. for fast iteration. Test it end-to-end in the current session.
2. **Release upstream once it works.** Copy the file into the upstream repo at `~/code/workdesk-os/config/<subdir>/`, run `/release` (PR → CI → merge → cut release → smoke against canary).

Until step 2 completes, treat the artifact as ephemeral. Don't depend on it from other skills, don't reference it in rules, don't onboard the operator to using it.

### 3. Don't depend on vault-local artifacts from upstream-tracked ones

This is a one-way dependency rule: upstream-tracked files (rules, skills, templates already in upstream) should not reference vault-local-only files (operator-customized scripts, vault-only schemas) via wikilinks or path references. The reference becomes broken in any other operator's vault.

Example of the bug: `config/rules/tools/keep-markdown.md` (upstream-tracked) references `config/sources/bookmark.md` (vault-local-only). Anyone running `/update` on a fresh vault gets the rule but not the source it cites. Fix: release `bookmark.md` upstream too, OR remove the citation from the rule.

### 4. After a `/update` reverts your work, suspect upstream drift first

If a file you created or modified vanishes, the most likely cause is `/update` having run between your write and your next check. Before re-creating from scratch:

- Check `/tmp/` for staging artifacts the prior session may have saved
- Check `.workdesk-backups/` for the snapshot taken before the apply
- Verify the upstream `config/` tree to see what state `/update` enforced

Then rebuild AND release upstream so it doesn't happen again.

### 5. Operator-improved upstream files get released as patches

If the vault has a strictly-better version of an upstream-tracked file (e.g., a script with a fix the operator added locally that never got upstream), the operator improvement is **at risk on every `/update`** — the upstream baseline overwrites the local improvement. Surface this via `diff` audit, then release a patch.

Example from 2026-06-02: `config/scripts/pre-tool-use-personal-lock.sh` in the vault had a word-boundary regex check while upstream still had the naive `*personal*` glob. Released as part of v1.10.0 before the next `/update` could overwrite the better version.

## What NOT to do

- **Don't iterate exclusively in vault and assume it persists.** Even if your specific path has survived several `/update` runs, behavior across paths is inconsistent. Plan for `/release` as part of the same task that creates the artifact, not as a separate cleanup pass later.
- **Don't `/release` before iteration is done.** Releasing half-baked work upstream pollutes the baseline for all operators (currently just the owner, but the discipline matters). Iterate in vault until the artifact passes its own acceptance test (skill runs end-to-end, rule's example holds, script's smoke-check passes), THEN release.
- **Don't release vault-local-only items in bulk without auditing them first.** Some vault-local items are operator-specific by design (e.g., `benali-deck` is a Benali-specific specialization that the operator wants to keep vault-local). Release deliberate; ask if any are intentional before bundling them into a rescue release.
- **Don't skip the canary smoke** at the end of a `/release` cycle, even for small additive changes. The smoke is what catches `/update` behavior changes that affect future operators.
- **Don't reference a vault-local-only file by path from an upstream-tracked one.** One-way dependency: upstream can know about other upstream, vault can know about both, but upstream can't know about vault-local-only. Broken references cascade.

## Source

- Session 2026-06-02 (`system/session-log/2026-06-02-gemini-transcript-pipeline-rewrite.md`) — session where this lesson was learned. Lost `/process-transcripts` rewrite AND `/get-transcripts` skill to `/update` twice; durable fix was three releases (v1.7.0, v1.9.0, v1.10.0).
- Related: [[claude-md-coevolution]] — for promotion of cross-skill `learnings.md` patterns to rules. This rule covers promotion of vault-local artifacts to upstream releases — the same shape, different layer.
