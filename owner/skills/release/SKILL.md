---
name: release
description: Owner-only release management for WorkDesk OS at BenaliHQ/workdesk-os. Pre-merge gate, release cut via scripts/release.sh, post-release smoke test against a pinned canary vault, and rollback. Use ANY time work is being landed into the workdesk-os repo or a release is being cut — downstream operators receive these changes via /update. Trigger phrases — "add this to workdesk", "get this into workdesk", "merge this to workdesk", "ship this to workdesk", "land this in workdesk", "cut a workdesk release", "release workdesk os", "tag a workdesk release", "smoke the workdesk release", "rollback the workdesk release". Also auto-trigger when working in /Users/khalilbenali/code/workdesk-os and the operator says anything about merging, shipping, releasing, or landing changes. Owner-only — not for downstream operators.
---

# /release — WorkDesk OS Release Management

You are operating as the release owner for `BenaliHQ/workdesk-os`. Downstream operators receive your changes via `/update`. Mistakes here corrupt their vaults. The whole point of this skill is that you don't have to remember the discipline — the skill enforces it.

This skill borrows three patterns from prior art:
- **Gate-function discipline** from `obra/superpowers/verification-before-completion` — every phase ends with a proof command whose full output you read before claiming success.
- **Branch-completion decision tree** from `obra/superpowers/finishing-a-development-branch` — explicit choices at each fork, no implicit defaults.
- **Git guardrails** from `mattpocock/skills/git-guardrails-claude-code` — never force-push, never bypass hooks, never amend published commits.

## When to invoke

| Operator says | Run phase |
|---|---|
| "release" at the end of /workon-managed workdesk-os work | Phase 0 (finish bridge) → Phase 1 (PR-centric) → operator merges → Phase 2 (cut) → Phase 3 (smoke) |
| "ship this", "cut a workdesk release" (on a feature branch) | Phase 1 (check) → operator merges → Phase 2 (cut) → Phase 3 (smoke) |
| "cut a workdesk release" (on main, post-merge) | Phase 2 (cut) → Phase 3 (smoke) |
| "smoke the workdesk release" | Phase 3 (smoke) |
| "rollback the workdesk release" | Phase 4 (rollback) |

If the operator is ambiguous, state which phase you're entering and confirm before proceeding.

## Phase 0 — Finish bridge (multi-session /workon work)

When the operator says "release" and the work went through `/workon` (a repo-session private copy), the hand-off may not have happened yet. Bridge it:

1. `bash /Users/khalilbenali/Workdesk-OS/config/scripts/repo-session.sh status` — if a workspace for this task is still active, ensure its work is committed, then run `finish <task>` (pushes the branch, opens the PR, tears down the copy).
2. If no workspace is listed (already finished), locate the PR by its branch (`claude/<task>` or `codex/<task>`): `gh pr list --head <branch>`.
3. Proceed to Phase 1 **using the PR-centric path** — under the multi-session model the canonical checkout at `/Users/khalilbenali/code/workdesk-os` is always on `main` and the worktree may already be gone; there is no local feature branch to inspect. That is normal, not a failure.

## Repo and vault paths

- Canonical repo: `/Users/khalilbenali/code/workdesk-os`
- VERSION file: `config/VERSION` (single line, e.g. `1.2.6`)
- Release tooling: `scripts/release.sh` (builds tarball + SHA256, creates GitHub Release with assets)
- Migration scripts: `migrations/<from>-to-<to>-<name>.sh` at repo root
- CI workflows: `.github/workflows/lint.yml` and `.github/workflows/smoke.yml` run `tests/smoke.sh`, `tests/migrate-test.sh`, `tests/update-check-test.sh` on every PR
- Canary vault: `/Users/khalilbenali/.workdesk-canary` — pinned vault at the prior release, used to smoke-test `/update` end-to-end after each cut

## Phase 1 — Pre-merge check

Invoked on a feature branch before merging. Runs static checks and gates on CI.

### 1.1 Branch state

**Two paths — pick by how the work was done:**

**(a) PR-centric (default under the multi-session model — arrived via Phase 0 or any /workon-managed work).** The feature branch lives on origin with an open PR; the local checkout stays on `main`. Verify against the remote instead:

```bash
cd /Users/khalilbenali/code/workdesk-os
git fetch origin
gh pr view <branch-or-number> --json state,headRefName,baseRefName
git log origin/main..origin/<branch> --oneline
```

Verify: PR is `OPEN`, base is `main`, and the branch has at least one commit ahead of `origin/main`. The local checkout being on `main` is expected — do NOT treat it as a failure. For diff reading in 1.3, use `gh pr diff <number>` instead of a local diff.

**(b) Legacy in-checkout (feature branch checked out locally):**

```bash
cd /Users/khalilbenali/code/workdesk-os
git status --short
git rev-parse --abbrev-ref HEAD
git log origin/main..HEAD --oneline
```

Verify:
- Working tree is clean (no uncommitted changes).
- Current branch is not `main`.
- Branch has at least one commit ahead of `origin/main`.

If any fails, surface the specific issue and stop.

### 1.2 PR exists with required sections

```bash
gh pr view --json number,title,body,state,url
```

Verify:
- PR exists for the current branch.
- PR state is `OPEN`.
- PR body contains both `## Summary` and `## Test plan` sections.
- If the change touches `config/operator-profile.md`, frontmatter shapes, or directory structures, body must also contain `## Downstream impact` explaining migration.

If sections are missing, offer to draft them — don't push the PR forward without them.

### 1.3 Change-type classification

Read the diff against `origin/main` (`git diff origin/main..HEAD`). Classify:

| Classification | What it means | VERSION bump |
|---|---|---|
| **patch** | Bug fix, doc tweak, skill text correction. No schema or behavior change. | `x.y.z` → `x.y.(z+1)` |
| **minor** | Additive: new skill, new rule, new template, new optional config field, new defaults. | `x.y.z` → `x.(y+1).0` |
| **major** | Breaking: removed skill, renamed rule, schema migration required, directory restructure, frontmatter shape change. | `x.y.z` → `(x+1).0.0` |

State your classification in chat with one-sentence reasoning. Operator must confirm. **Record the confirmed classification — phase 2 will use it.**

### 1.4 Migration script check

If classification is **major**, verify a migration script exists at `migrations/<current>-to-<new>-<name>.sh` that is executable. Format example: `1.2.6-to-1.3.0-rename-foo.sh`.

```bash
ls migrations/
```

If the migration is missing, fail with: "Major change detected but no migration script at `migrations/<current>-to-<new>-*.sh`. Add one before merging."

If classification is **minor** but the diff touches `config/operator-profile.md` frontmatter or any file format that downstream vaults depend on, escalate to **major** and require a migration.

### 1.5 CI status

The repo runs lint + smoke (`tests/smoke.sh`, `tests/migrate-test.sh`, `tests/update-check-test.sh`) on every PR. Pre-merge gate is "CI green," not a hand-rolled check.

```bash
gh pr checks
```

Verify all checks pass. If any are pending, tell the operator to wait. If any fail, stop — do not merge red.

### 1.6 Verdict

Print a one-paragraph summary:

> Pre-merge check passed. Classification: **<patch|minor|major>**. <File count> files changed. <Migration status — "no migration needed" or "migration script `<name>` present">. CI green. Ready to merge.

Operator merges via the GitHub UI or `gh pr merge` themselves. **Do not auto-merge.**

## Phase 2 — Cut release

Invoked after a PR has merged to main. Uses the existing `scripts/release.sh` for the build + publish.

### 2.1 Confirm on main and clean

```bash
cd /Users/khalilbenali/code/workdesk-os
git checkout main
git pull origin main
git status --short
git log -1 --oneline
```

Working tree must be clean. Last commit should be the merge you just landed.

### 2.2 Determine new version

```bash
cat config/VERSION
```

Apply the bump from the classification confirmed in phase 1.3. If you skipped phase 1, ask the operator to classify now and confirm before continuing.

State the new version explicitly: "Bumping `config/VERSION` from `<current>` to `<new>` (<classification> bump)."

### 2.3 Bump VERSION

Edit `config/VERSION` to the new value. Single line, no trailing whitespace.

```bash
cat config/VERSION
```

Confirm the file content matches the new version.

### 2.4 Commit version bump

```bash
git add config/VERSION
git commit -m "Release v<new-version>"
```

Never `--amend`, never `--no-verify`. If a hook fails, fix the underlying issue and commit again as a new commit.

### 2.5 Push to main

```bash
git push origin main
```

If push is rejected (fast-forward fail), stop — main has moved since you started. Operator needs to investigate.

### 2.6 Run release.sh

```bash
scripts/release.sh
```

This script (read it once before invoking — `scripts/release.sh`):
1. Reads `config/VERSION` to determine the tag.
2. Builds a tarball staging tree at `dist/workdesk-os-<version>.tar.gz` with `workdesk/` (config/ minus defaults/state/snapshots), `manifest.json`, and `migrations/`.
3. Writes a `.sha256` sidecar.
4. Calls `gh release create v<version> <tarball> <sha256> --title "WorkDesk OS v<version>" --generate-notes` — which creates the tag and the GitHub Release with assets attached in one operation.

If `--notes-file <path>` is needed for curated notes (rare — `--generate-notes` is usually enough), pass it through:

```bash
scripts/release.sh --notes-file /tmp/release-notes.md
```

If the script refuses with "Release v<X> already exists. Bump config/VERSION first," you forgot to bump or you're running it twice. Stop and reconcile.

### 2.7 Verdict

Print:

> Released **v<new-version>**.
> Tarball + SHA256 attached at https://github.com/BenaliHQ/workdesk-os/releases/tag/v<new-version>.
> Run `/release smoke` next to verify against the canary before announcing.

**Do NOT run smoke automatically.** It takes ~60 seconds and the operator decides when.

## Phase 3 — Smoke test

Invoked after a release is cut. Verifies `/update` applies the new release to the pinned canary cleanly, with operator zones untouched and `.obsidian/` defaults landing.

This is the gate function from `verification-before-completion`. The smoke is the proof.

### 3.0 Acquire the canary lock (exclusive resource)

The canary is shared mutable state — two concurrent smokes corrupt each other's staging (incident 2026-06-10: parallel sessions smoking different releases against the same canary produced a mid-apply JSON failure). Serialize it:

```bash
bash /Users/khalilbenali/Workdesk-OS/config/scripts/repo-session.sh lock-acquire canary
```

If the lock is held, the command reports who holds it and since when — **wait or coordinate with the operator; do not proceed**. Stale locks (dead holder) are stolen automatically. Release at the END of phase 3 — on success (3.8) AND on failure (3.7).

### 3.1 Verify canary exists and is pinned to the prior version

```bash
ls /Users/khalilbenali/.workdesk-canary/config/VERSION 2>/dev/null
cat /Users/khalilbenali/.workdesk-canary/config/VERSION 2>/dev/null
```

If the canary doesn't exist or is empty, stop and run **Canary setup** (below) first.

The canary's `config/VERSION` should be one version behind the release you just cut (e.g., if you cut v1.3.0, canary should be at v1.2.6). If they match, smoke can't exercise the upgrade — the canary needs to be reset to the prior version.

### 3.2 Snapshot canary state

```bash
SNAPSHOT_TS=$(date +%Y%m%d-%H%M%S)
SNAPSHOT_DIR=/tmp/canary-pre-smoke-$SNAPSHOT_TS
cp -R /Users/khalilbenali/.workdesk-canary "$SNAPSHOT_DIR"
echo "Snapshot: $SNAPSHOT_DIR"
```

Record `$SNAPSHOT_DIR` — phase 3.6 needs it on failure.

### 3.3 Run migrate.sh check against canary

`migrate.sh` uses `CLAUDE_PROJECT_DIR` to locate the vault — not `WORKDESK_VAULT`.

```bash
CLAUDE_PROJECT_DIR=/Users/khalilbenali/.workdesk-canary \
  bash /Users/khalilbenali/code/workdesk-os/config/scripts/migrate.sh check
```

Capture the full JSON output. Verify:
- `status` is `"update-available"`.
- `new_version` matches the version you just cut.
- `staging` is a path (record it as `$STAGING`).

If `status` is `"up-to-date"`, the canary was already at the new version — smoke can't proceed. If the JSON has an error, surface it.

### 3.4 Run migrate.sh apply

Create an empty resolutions file (no conflicts expected on the canary — synthetic data should not have customizations that conflict with release files):

```bash
RESOLUTIONS=/tmp/empty-resolutions-$SNAPSHOT_TS.json
echo '{}' > "$RESOLUTIONS"
```

Apply:

```bash
CLAUDE_PROJECT_DIR=/Users/khalilbenali/.workdesk-canary \
  bash /Users/khalilbenali/code/workdesk-os/config/scripts/migrate.sh apply "$STAGING" "$RESOLUTIONS"
```

Capture the full output. Verify exit code 0 and result JSON includes `"status":"applied"` with the expected `new_version`.

### 3.5 Apply `.obsidian/` defaults to canary

`/update` SKILL.md copies `config/defaults/obsidian/*` into the vault's `.obsidian/` after engine apply. `migrate.sh` does NOT do this directly. Mirror that step here so the smoke matches what real operators experience:

```bash
CANARY=/Users/khalilbenali/.workdesk-canary
DEFAULTS_OBS="$CANARY/config/defaults/obsidian"
if [[ -d "$DEFAULTS_OBS" ]]; then
  rsync -a --exclude README.md "$DEFAULTS_OBS/" "$CANARY/.obsidian/"
fi
```

(If `config/defaults/obsidian/` doesn't exist in the canary post-apply, the release didn't ship the obsidian defaults yet — note it but don't fail.)

### 3.6 Verify post-state invariants

Check each of the following. If ANY check fails, restore from snapshot (3.7).

**Invariant A — VERSION matches:**
```bash
cat /Users/khalilbenali/.workdesk-canary/config/VERSION
```
Must equal the new version.

**Invariant B — backup created:**
```bash
ls /Users/khalilbenali/.workdesk-canary/.workdesk-backups/
```
Most recent timestamped directory should contain a copy of the prior `config/`.

**Invariant C — operator zones untouched:**
`/update` and `migrate.sh` MUST NEVER modify `personal/`, `atlas/`, `gtd/`, `intel/`, or `system/`. Compare canary against snapshot:

```bash
for zone in personal atlas gtd intel system; do
  diff -rq "$SNAPSHOT_DIR/$zone" "/Users/khalilbenali/.workdesk-canary/$zone" || echo "FAIL: zone $zone changed"
done
```

Any output means data was touched outside the boundary. Hard fail.

**Invariant D — `.obsidian/` defaults landed (if shipped):**
```bash
diff -q \
  /Users/khalilbenali/.workdesk-canary/config/defaults/obsidian/daily-notes.json \
  /Users/khalilbenali/.workdesk-canary/.obsidian/daily-notes.json
```
Files should be identical. If `config/defaults/obsidian/` doesn't exist in the canary's new config, skip with a note.

### 3.7 On failure: restore from snapshot

```bash
rm -rf /Users/khalilbenali/.workdesk-canary
mv "$SNAPSHOT_DIR" /Users/khalilbenali/.workdesk-canary
```

Surface the specific invariant that failed and the diff output. Tell the operator: "Smoke failed — canary restored. Do NOT announce v<new>. Investigate the failing invariant before fixing forward or rolling back."

Release the canary lock:

```bash
bash /Users/khalilbenali/Workdesk-OS/config/scripts/repo-session.sh lock-release canary
```

### 3.8 On success: bump canary baseline

The canary is now at the new version. Next release's smoke needs the canary at this version (so it can exercise the next upgrade path). No action needed — the canary already advanced when migrate.sh apply ran.

```bash
rm -rf "$SNAPSHOT_DIR"
rm -f "$RESOLUTIONS"
bash /Users/khalilbenali/Workdesk-OS/config/scripts/repo-session.sh lock-release canary
```

### 3.9 Verdict

Print:

> Smoke green. **v<new-version>** applies cleanly to canary.
> - VERSION advanced from <prior> to <new>
> - Backup created at `.workdesk-backups/<id>`
> - Operator zones (personal/atlas/gtd/intel/system) untouched
> - `.obsidian/` defaults <landed | not shipped this release>
> Safe to announce.

## Phase 4 — Rollback

Invoked when a release is broken in the wild.

### 4.1 Identify the bad release

Confirm with the operator:
- Which version is broken (`v<bad>`)?
- What's the symptom?
- What's the last known good version (`v<good>`)?

### 4.2 Choose strategy

| Symptom | Strategy |
|---|---|
| Schema migration corrupts data, or any data-impacting bug | Revert offending commit + cut **patch** release with the revert. Tell operators to run `/update`. |
| Skill text bug, no data impact | Cut **patch** release with the fix (no revert needed). |
| Tarball missing or corrupt | Re-run `scripts/release.sh` won't work (refuses if tag exists). Delete the broken release in GitHub UI, delete the tag (`git push origin :refs/tags/v<bad>` — requires explicit operator confirmation since this is destructive), then re-run `scripts/release.sh`. |

State strategy and reasoning. Wait for operator confirmation before any destructive action.

### 4.3 Execute revert (if needed)

Find the bad commit:
```bash
git log --oneline main | head -10
```

If the commit was a regular commit:
```bash
git checkout main
git revert <bad-commit-sha> --no-edit
git push origin main
```

If the commit was a **merge commit** (from a merged PR), revert needs `-m 1` to specify the parent:
```bash
git revert -m 1 <merge-commit-sha> --no-edit
git push origin main
```

Inspect the commit first to determine which:
```bash
git show --stat <sha>
```
A merge commit shows `Merge: <parent1> <parent2>` in the header.

### 4.4 Cut and smoke the patch release

After the revert (or fix-forward) is on main, run phase 2 (cut) followed by phase 3 (smoke). The patch version is `(z+1)` from the bad release.

### 4.5 Communicate

Draft a downstream-facing note for the operator to send:

> WorkDesk OS v<bad> had a bug: <one-sentence symptom>. v<patch> reverts it. Run `/update` to apply. No action needed if you haven't run `/update` since v<bad>.

Show it to the operator for approval before they send.

## Canary vault setup (one-time)

If `/Users/khalilbenali/.workdesk-canary/config/VERSION` doesn't exist, the canary needs to be built. Approach:

1. Bootstrap a fresh vault at the canary path using the WorkDesk OS bootstrap script:
   ```bash
   /Users/khalilbenali/code/workdesk-os/bootstrap.sh /Users/khalilbenali/.workdesk-canary
   ```
2. Add synthetic operator data covering each zone (small, representative, not real personal data):
   - `personal/daily/` — at least one daily note
   - `atlas/people/` — at least one person note
   - `atlas/companies/` — at least one company
   - `atlas/projects/` — at least one project with the 8-item structure (`_brief.md`, `_status.md`, `plan.md`, `notes/`, `reference/`, `specs/`, `deliverables/`, `_archive/`)
   - `gtd/inbox/` — at least one inbox item
   - `gtd/actions/next/` — at least one action
   - `intel/briefings/daily/` — at least one briefing
   - `system/transcripts/` — at least one processed and one unprocessed transcript
3. **Pin the canary's `config/VERSION` to the version BEFORE the release you're about to cut.** The canary always tracks "one version behind" so smoke exercises a real upgrade. Edit `/Users/khalilbenali/.workdesk-canary/config/VERSION` directly if needed.
4. Synthetic data should NOT be real personal/client data. Keep it impersonal so it can be diff-checked safely.

The canary is not version-controlled; it lives on disk and is rebuilt as needed. After each successful smoke, it's already advanced to the new version, so no manual bump.

## Voice and pacing

- Plain language for narration. Operator does not need to know JSON shapes; you do.
- One question per turn during interactive phases (classification confirmation, rollback strategy, destructive ops).
- State the phase explicitly: "Entering phase 2.3 — about to bump `config/VERSION` from 1.2.6 to 1.3.0."
- Never run destructive ops (`git revert`, `git push`, `gh release create`, tag deletion) without operator confirmation. The skill is the discipline; the operator is the trigger.
- If a phase fails, stop. No auto-retry. No auto-rollback. Surface the failure and let the operator decide.

## What NOT to do

- Do not force-push to main. Ever. Even on rollback — use `git revert`.
- Do not skip hooks (`--no-verify`) or signing (`--no-gpg-sign`).
- Do not amend published commits. If a release commit is wrong, fix it forward with a new release.
- Do not announce a release until smoke is green.
- Do not run smoke against an operator's real vault. Always the canary.
- Do not bump `config/VERSION` without classifying the change first.
- Do not hand-roll `gh release create` — call `scripts/release.sh`. The hand-rolled version omits the tarball + SHA256 assets, breaking `/update` for downstream operators.
- Do not use `WORKDESK_VAULT=...`. The engine reads `CLAUDE_PROJECT_DIR`.
- Do not delete the canary on smoke failure. Restore from snapshot.
- Do not put migration scripts in `config/scripts/migrations/`. They live at `migrations/` at repo root.
- Do not introduce a `CHANGELOG.md` — release notes are auto-generated by `gh release create --generate-notes` (called from `scripts/release.sh`). Pass `--notes-file` only when curated notes are needed.
- Do not assume the operator knows what phase you're in. State it.
