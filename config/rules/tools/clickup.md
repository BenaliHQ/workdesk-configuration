# ClickUp — Tool Reference

ClickUp is a project-management tool that many teams also use as their internal-comms surface (tasks, per-client lists, reviews, and Chat channels all in one place). Claude reaches it through the **`clickup` CLI** — a Go binary built for agent workflows that returns JSON by default — with **raw `curl` against the ClickUp REST API** as the fallback for the endpoints the CLI doesn't wrap, notably ClickUp Chat (v3) and the workspace-wide filtered-task endpoint.

## Access Method

| Layer | Path | Covers |
|---|---|---|
| CLI | `~/.local/bin/clickup` (or wherever the binary lives on PATH) | tasks, lists, folders, spaces, comments, checklists, docs (v3), custom fields, time entries, tags, members, templates, goals, attachments |
| REST v2 | `https://api.clickup.com/api/v2` | `GET /team` (workspace list), `GET /team/{id}/task` (workspace-wide filtered tasks) — neither has a CLI equivalent |
| REST v3 | `https://api.clickup.com/api/v3` | Chat channels + messages — no CLI equivalent |

**Workspace and space IDs are resolved at runtime**, from the token, by every script in this layer. Don't hardcode them and don't cache them in this file — teams rename and reorganize spaces, and a stale ID reads as an empty result rather than an error. If it's useful to write your workspace map down, put it in the relevant business or client note in `atlas/` (operator zone), not here.

## Setup

1. Install the CLI. It's distributed as a Go binary; drop it on PATH (commonly `~/.local/bin/clickup`).
2. Create a personal API token in ClickUp: **Settings → Apps → API Token**. It looks like `pk_…`.
3. Write it to `~/.clickup-cli.yaml`:

   ```yaml
   token: pk_…
   workspace: ""
   ```

4. Verify: `clickup auth whoami` returns your user object.

The CLI reads that file automatically — no flags needed. Scripts and `curl` calls read the same file, or take `$CLICKUP_TOKEN` as an override.

Personal tokens don't expire on a schedule, but they die if regenerated. On a `401`, the fix is always the same: regenerate the token and update `~/.clickup-cli.yaml`. Don't debug further.

> [!warning]
> A ClickUp personal token grants full read **and write** access to every workspace the account can see. Treat it like a password. It sits in plaintext on disk, so it is not mirrored to Infisical by default — extending the [[infisical]] tool-state sync pattern to ClickUp is an open enhancement, not a shipped one.

## Common Commands

Set `CU=~/.local/bin/clickup` first. Every command returns JSON; add `--format text` for human-readable output.

| Command | What it does |
|---|---|
| `$CU auth whoami` | Confirm auth (smoke test) |
| `$CU space list --workspace <workspace-id>` | List spaces |
| `$CU list list --space <space-id>` | Lists directly in a space |
| `$CU folder list --space <space-id>` | Folders (each carries nested lists) |
| `$CU task list --list <list-id> --include-closed --include-markdown` | Tasks in a list, with descriptions |
| `$CU task list --list <list-id> --date-updated-gt <unix-ms>` | Tasks touched since a timestamp |
| `$CU task get --task <task-id>` | Single task, full detail |
| `$CU comment list --task <task-id>` | Comments on a task |
| `$CU doc list --workspace <workspace-id>` | ClickUp Docs (v3) |
| `$CU member list --list <list-id>` | Who's on a list |

`task list` filters worth knowing: `--assignee`, `--status`, `--tag`, `--subtasks`, `--include-closed`, `--date-created-gt`, `--date-done-gt`, `--due-date-lt`, `--order-by`, `--page`. All dates are **Unix milliseconds**, not seconds.

### Endpoints with no CLI equivalent

```bash
TOK=$(awk '/^token:/{print $2}' ~/.clickup-cli.yaml)
WS=<workspace-id>

# Workspaces (this is how you discover the workspace id in the first place)
curl -s -H "Authorization: $TOK" https://api.clickup.com/api/v2/team

# Workspace-wide tasks touched since a timestamp (the activity backbone)
curl -s -H "Authorization: $TOK" \
  "https://api.clickup.com/api/v2/team/$WS/task?date_updated_gt=<ms>&include_closed=true&subtasks=true"

# Chat channels (sorted by latest_comment_at) and one channel's messages
curl -s -H "Authorization: $TOK" \
  "https://api.clickup.com/api/v3/workspaces/$WS/chat/channels?limit=100"
curl -s -H "Authorization: $TOK" \
  "https://api.clickup.com/api/v3/workspaces/$WS/chat/channels/<channel-id>/messages?limit=50"
```

## The activity digest

`config/scripts/clickup-digest.py` is the read-only wrapper that answers "what did the team do and say?" It merges task movement, task comments, and chat messages into one structured payload.

```bash
python3 config/scripts/clickup-digest.py --days 3 --markdown
python3 config/scripts/clickup-digest.py --days 7 --space "<space name>"
python3 config/scripts/clickup-digest.py --since 2026-01-15 --include-dms
python3 config/scripts/clickup-digest.py --days 2 --no-chat   # JSON, tasks + comments only
```

Behavior worth knowing:

- **Read-only by construction.** No write verbs anywhere in the script. Safe to run unattended.
- **DMs are excluded by default.** `--include-dms` opts in. Public channels only otherwise.
- Resolves user IDs to names and rewrites `[@Name](#user_mention#123)` markup to plain `@Name`; replaces inline image markup with `[attachment]`.
- Splits tasks into "checked off" (status type `closed`/`done`) and "moved."
- Comments are only fetched for tasks that appear in the window, capped at `--comment-cap` (default 40) to bound the request count.
- Fetch failures land in an `errors` object rather than killing the run — a chat permission failure still returns the task digest.

Feed the JSON to Claude for synthesis; use `--markdown` to read the raw digest directly. The operator-facing entry point is the `/team-pulse` skill, which wraps this script, adds vault context, and routes actions per [[gtd-inbox-processing]].

## The new-work detector

`config/scripts/clickup-new-work.py` snapshots the ClickUp space/folder/list inventory to `config/state/clickup-inventory.json` and flags anything new that no vault project appears to cover.

```bash
python3 config/scripts/clickup-new-work.py            # detect + write [REVIEW] inbox items
python3 config/scripts/clickup-new-work.py --dry-run  # report only
python3 config/scripts/clickup-new-work.py --seed     # re-baseline, flag nothing
```

- **Self-seeds on first run** — with no state file it records the baseline and flags nothing, instead of dumping every existing folder into the inbox at once.
- **A new folder is one item, not one per list.** Its `Task List` / `Meeting List` / `Deliverables` siblings are suppressed as routine, as are GTD-shaped list names (`Inbox`, `Next Actions`, `Waiting On`, `Someday Maybe`, `Reference`).
- **Excludes personal GTD and template spaces by default** — any space named `GTD …`, plus `Templates & Processes`. Those are individuals' own boards, not project work. `--all-spaces` overrides.
- **Fuzzy-matches against existing vault project and client slugs** (`atlas/clients/`, `atlas/businesses/`, `atlas/projects/`, `gtd/projects/`). A likely match is noted in the inbox item so the answer can be "link it to the existing project" rather than "make a new one."
- Inbox items follow [[inbox-item-format]] and carry the ClickUp entity ID in frontmatter. Flagged IDs are recorded in state, so declining an item doesn't get it re-flagged.
- **To run it daily**, wire it to a scheduler. On macOS use a LaunchAgent rather than crontab (cron runs with a stripped environment outside the logged-in user session), pointing at `/usr/bin/python3` and the script's absolute path, with `WorkingDirectory` set to the vault and stdout/stderr redirected to `system/`. `/team-pulse` also runs the detector, so an operator who runs pulses regularly doesn't strictly need the schedule.

Detection is the automatic part; **scaffolding a project is not.** The detector never creates a project folder — it writes a `[REVIEW]` item and waits for the operator.

## Writing to ClickUp

**Default posture: confirm every single write.**

A ClickUp personal token has full write access to the whole workspace, and anything Claude does there is immediately visible to every teammate. Before any write: state the verb, the target task or list by name, and the literal text of any comment, then wait for the operator's go-ahead. One confirmation per action — approval to close one task is never approval to close its siblings. Never batch a write with other work in the same tool call. Reads need no confirmation.

```bash
CU=~/.local/bin/clickup
$CU task create --list <list-id> --name "..." --description "..."
$CU task update --task <task-id> --status "..."
$CU comment create --task <task-id> --comment-text "..."
```

Check `--help` per subcommand before running; flags differ.

## Known Limitations

- **No CLI chat support.** ClickUp Chat is v3-only and the CLI doesn't wrap it — chat always goes through `curl` or the digest script.
- **Chat message authorship is thin.** The messages endpoint returns a user ID, not a nested user object; names come from the workspace member map. A message from someone no longer in the workspace resolves to a bare ID.
- **Comment volume is unbounded per task.** Teams that paste full meeting recaps into task comments produce comments thousands of words long. Truncate before feeding many of them into one context.
- **`GET /team/{id}/task` paginates at 100** and only surfaces tasks the token can see. It's scoped by `date_updated_gt`, so a task edited outside the window is invisible even if its comments are new.
- **One workspace often holds several businesses,** separated only by space. Always scope by space before reporting, or a report about one line of business quietly includes another's churn.
- **The MCP connector is a separate path.** A ClickUp MCP server may be available in Claude.ai sessions. Interactive OAuth connectors are unavailable in headless and scheduled runs, which is why this layer uses the CLI + token. If both paths are in play in one org, decide deliberately which surface uses which; don't consolidate by accident.

## Common Mistakes

- **Passing seconds where ClickUp wants milliseconds.** Every date filter is Unix ms. A seconds value silently returns everything (or nothing).
- **Reporting workspace-wide activity as one business's activity.** Scope by space.
- **Writing to ClickUp without confirmation.** Creating, closing, or commenting on a task is outward-facing work visible to the whole team — confirm first, every time.
- **Hardcoding space or list IDs.** Re-list before targeting; teams reorganize.
- **Reading DMs into a shared artifact.** DMs are excluded from the digest by default for a reason; don't quote them into a vault note or a team-visible summary without the operator saying so.

## Detection clause

Surface proactively when:

- The operator asks what the team is working on, what got finished, what they missed, or what's stuck — run the digest instead of asking them to summarize.
- The operator is about to plan or scope work that already has a ClickUp list — pull the live list before planning from vault memory alone. ClickUp is production for task state; vault `_status.md` lags it.
- A vault project's `_status.md` is stale (>14 days per [[per-project-accounting]]) and a matching ClickUp list exists — offer to reconcile from ClickUp.
- The operator references a task, review, or comment by name — resolve it against ClickUp rather than guessing at its state.
- A `401` comes back — the personal token was regenerated; don't debug further, just say so.

## Sources

- ClickUp API docs: https://developer.clickup.com/reference (v2), https://developer.clickup.com/docs (v3 chat)
- The `clickup` CLI's own `--help` is authoritative on flags.
- Related: [[infisical]] (where the token could be mirrored), [[gws]] (same CLI-over-MCP preference for a tool with both surfaces)
