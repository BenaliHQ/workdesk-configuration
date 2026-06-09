# No Silent Destruction

You never run a destructive operation silently. Every destructive operation requires (1) **explicit operator confirmation in their own words**, (2) a **snapshot of the affected target taken first**, and (3) execution as **its own tool call**, never batched with non-destructive work. This rule is the operator-permission gate for destruction, the sister of [[no-silent-scaffolding]] (the gate for creation).

A mechanical PreToolUse hook at `~/.claude/hooks/destructive-guard.sh` enforces a subset of this rule for the Bash tool. The hook is the floor, not the ceiling — the rule applies even when no hook fires.

## When this applies

Anytime you're about to run an operation that destroys, removes, overwrites, or makes a non-trivially-reversible change to:

- Files or directories in operator-owned areas (`~/Workdesk-OS/`, `~/<primary-vault>/`, `~/Projects/`, `~/code/`, `~/.claude/`)
- Skills, plugins, or marketplaces (`npx skills remove`, `npm uninstall -g`, plugin removal)
- Git history (`git reset --hard`, `git push --force`, `git clean -fdx`, force-deleted branches/tags/refs)
- Vercel projects, deployments, or other live services (`vercel remove`, `vercel rm`, dashboard deletions performed via API)
- Operator config (`~/.claude/settings.json`, `~/.claude/CLAUDE.md`, brand spec files, design tokens)
- Databases (any `DROP`, `DELETE WHERE`, `TRUNCATE`, schema changes)
- Cloud resources (S3 buckets, Vercel projects, DNS records, etc.)

Also applies to non-Bash destructive operations not caught by the hook — e.g., `Edit`/`Write` calls that overwrite operator content beyond what was explicitly requested.

## What to do

Three things, in this order, every time:

### 1. State the destruction plainly to the operator

Name **exactly** what will be destroyed — path, count, scope — and **wait for explicit confirmation in their own words**. Acceptable: "yes delete these 24 files at `/path/x`," "go ahead nuke the project." Not acceptable: parsing earlier ambiguous approval, inferring consent from a sequence like "fix the install" → "remove + reinstall."

### 2. Snapshot first

Before executing, take a backup of the affected target into `/tmp/predestructive-<unix-timestamp>/`:

```bash
cp -a <target-path> /tmp/predestructive-$(date +%s)/
```

Even for "small" deletions. A snapshot costs milliseconds; recovery without one costs operator trust.

### 3. Run as its own tool call

Destructive operations never share a Bash tool call with anything else. Don't chain `rm` with the reinstall. Don't sed-in-place inside a multi-command bash block. Each destruction is its own call with a description that names exactly what's being destroyed.

### 4. Use the hook's override marker correctly

When the destructive-guard hook blocks a command, retrying with `# OPERATOR_CONFIRMED_DESTRUCTIVE` appended is the receipt **after** completing steps 1-3. The marker is not a workaround — it's an audit log that the operator confirmed and a snapshot was taken. Using it without doing 1-3 defeats the entire safeguard.

### 5. Read flag semantics literally

If `--help` says `--all = --skill '*' --agent '*'`, then `--all` means *all of everything*, not "all of the named target." Do not paper over flag semantics with the surrounding context. The 2026-05-28 incident was exactly this failure.

## What NOT to do

- Do not run `npx skills remove` (or any other manager's wildcard remove) with `--all`, `-s '*'`, or any glob, even when you "only mean" the just-installed thing.
- Do not run `rm -rf` against any path under operator-owned areas without steps 1-3.
- Do not run `git push --force` (or `--force-with-lease`) without steps 1-3.
- Do not `git reset --hard`, `git clean -fdx`, `git branch -D`, or `git checkout -- .` without steps 1-3.
- Do not pipe `find` to `-delete` or to `xargs rm` in operator-owned areas.
- Do not redirect (`>`) into `~/.claude/settings.json`, `CLAUDE.md`, brand spec files, or any other operator-critical config — use `Edit` for surgical changes.
- Do not batch a destructive operation with a recovery, install, or other "useful" operation in the same Bash tool call.
- Do not infer operator consent from a vague approval upstream. Re-confirm at the moment of destruction.
- Do not assume the hook will catch you. The hook catches *some* patterns, not all. The rule applies regardless of whether the hook fires.

## Mechanical enforcement

The PreToolUse hook at `~/.claude/hooks/destructive-guard.sh` enforces:

- **Hard-block** (no override): `rm -rf /`, `rm -rf $HOME`, fork bombs, raw-disk `dd`, `mkfs.*`, raw writes to `/dev/sda` style targets.
- **Guard** (blocks; allows after marker + operator confirmation): skill manager wildcards, `git push --force`, `git reset --hard`, `rm -rf` in operator areas, `find -delete` in operator areas, `xargs rm`, redirects into `~/.claude/settings.json` / `CLAUDE.md`.

Confirmed destructive executions are logged to `/tmp/destructive-guard-log/confirmed.log`.

## Source

- Operator instruction 2026-05-28: "Will you please make sure that this never happens again and figure out why you did that? You need to stop doing that ever again." Triggered by an incident the same day in which `npx skills remove autoresearch --all -y` removed all 24 vault skills because `--all` expanded to `--skill '*' --agent '*'`, not "all components of autoresearch." Full root-cause and the mechanical guard are documented at `~/.claude/hooks/destructive-guard.sh`.

Related: [[no-silent-scaffolding]] (sister rule — the gate for creation); [[type-scaffolding]]; [[instance-scaffolding]]; the `/careful` skill (interactive variant for terminal-issued commands).
